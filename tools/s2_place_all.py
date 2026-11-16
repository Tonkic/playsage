"""Full 9-chip puzzle placement, standalone in session 2.

Placement-then-verify: drag chip to target centroid, release, then read the
board matrix (solid colors are reliable) and press R on the selected chip
until its cells match the plan; delete + retry once if hopeless.
"""
import ctypes
import json
import sys
import time

import pyautogui
from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False


def game_client_origin():
    """Client-area origin of the VISIBLE game window on screen."""
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if "星穹铁道" in buf.value:
            found.append(hwnd)
        return True

    user32.EnumWindows(cb, None)
    if not found:
        raise RuntimeError("game window not found")
    hwnd = found[0]

    class PT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = PT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


WL, WT = game_client_origin()
print("window client origin:", WL, WT, flush=True)
GX0, GY0, GW, GH = 670.5, 273.0, 79.3, 84.5
TAB_GRID = (1410, 180)
TAB_STAR = (1552, 180)

# solver layout (39 cells, no overlap)
LAYOUT = {
    "L_ld":  {"tab": "grid", "slot": (1432, 345), "cells": [(0,0),(0,1),(0,2),(1,1),(1,2)]},
    "P_z1":  {"tab": "grid", "slot": (1672, 345), "cells": [(5,1),(5,2),(5,3),(6,1),(6,2)]},
    "P_z2":  {"tab": "grid", "slot": (1672, 345), "cells": [(0,4),(0,5),(1,4),(1,5),(2,5)]},
    "T_ld":  {"tab": "star", "slot": (1432, 345), "cells": [(1,0),(2,0),(2,1),(3,0)]},
    "L_zhg": {"tab": "star", "slot": (1672, 345), "cells": [(0,3),(1,3),(2,2),(2,3)]},
    "Z_xb1": {"tab": "grid", "slot": (1432, 780), "cells": [(2,4),(3,4),(3,5),(4,5)]},
    "Z_xb2": {"tab": "star", "slot": (1672, 562), "cells": [(5,4),(5,5),(6,3),(6,4)]},
    "S_xb":  {"tab": "star", "slot": (1672, 780), "cells": [(3,1),(4,0),(4,1),(5,0)]},
    "S_ld2": {"tab": "grid", "slot": (1672, 562), "cells": [(3,2),(3,3),(4,3),(4,4)]},
}
ORDER = ["L_ld", "P_z1", "P_z2", "T_ld", "L_zhg", "Z_xb1", "Z_xb2", "S_xb", "S_ld2"]
FREE_CELL = (6, 0)


def grab():
    return ImageGrab.grab().convert("RGB")


def board_matrix(img):
    sx = img.width / 1920.0
    sy = img.height / 1080.0
    out = []
    for r in range(6):
        line = []
        for c in range(7):
            wx, wy = WL + GX0 + GW * (c + 0.5), WT + GY0 + GH * (r + 0.5)
            x, y = int(wx * sx), int(wy * sy)
            votes = {}
            for dx, dy in ((0, 0), (-12, 0), (12, 0), (0, -9), (0, 9)):
                xx, yy = int(x + dx * sx), int(y + dy * sy)
                if xx >= img.width or yy >= img.height:
                    continue
                rr, gg, bb = img.getpixel((xx, yy))
                if rr > 200 and 150 < gg < 230 and 60 < bb < 120: k = "Y"
                elif rr > 200 and 150 < gg < 220 and 150 < bb < 220: k = "P"
                elif bb > 200 and 150 < gg < 230 and 100 < rr < 180: k = "B"
                elif 60 < rr < 115 and 60 < gg < 120 and 80 < bb < 145: k = "F"
                elif rr < 75 and gg < 80 and bb < 95: k = "."
                else: k = "?"
                votes[k] = votes.get(k, 0) + 1
            if votes.get("F"): k = "F"
            elif votes.get("Y", 0) >= 2: k = "Y"
            else: k = max(votes, key=votes.get)
            line.append(k)
        out.append(line)
    return out


def cells_filled(matrix, cells):
    bad = [(c, r) for c, r in cells if matrix[r][c] not in ("P", "B", "?", "Y", "t")]
    return not bad


def wpt(c, r):
    return (WL + GX0 + GW * (c + 0.5), WT + GY0 + GH * (r + 0.5))


def slow_drag(from_xy, to_xy, steps=24):
    pyautogui.moveTo(from_xy[0] + WL, from_xy[1] + WT)
    time.sleep(0.35)
    pyautogui.mouseDown()
    time.sleep(0.3)
    for i in range(1, steps + 1):
        pyautogui.moveTo(from_xy[0] + WL + (to_xy[0] - from_xy[0]) * i / steps,
                         from_xy[1] + WT + (to_xy[1] - from_xy[1]) * i / steps)
        time.sleep(0.05)
    time.sleep(0.4)
    pyautogui.mouseUp()
    time.sleep(0.9)


def main():
    done = {}
    current_tab = None
    for chip in ORDER:
        info = LAYOUT[chip]
        target = [tuple(c) for c in info["cells"]]
        tx = sum(p[0] for p in target) / len(target)
        ty = sum(p[1] for p in target) / len(target)
        tpt = wpt(tx, ty)

        if info["tab"] != current_tab:
            tab_xy = TAB_GRID if info["tab"] == "grid" else TAB_STAR
            pyautogui.click(tab_xy[0] + WL, tab_xy[1] + WT)
            time.sleep(1.2)
            current_tab = info["tab"]

        placed = False
        for attempt in range(2):
            slow_drag(info["slot"], tpt)
            # verify: are ALL target cells now filled?
            matrix = board_matrix(grab())
            if cells_filled(matrix, target):
                print(f"[{chip}] placed attempt {attempt}", flush=True)
                placed = True
                break
            # maybe rotated wrong: the placed chip is selected -> press R to spin it
            for rot in range(4):
                pyautogui.press("r")
                time.sleep(0.55)
                matrix = board_matrix(grab())
                if cells_filled(matrix, target):
                    print(f"[{chip}] placed after R{rot+1}", flush=True)
                    placed = True
                    break
            if placed:
                break
            # delete the wrongly placed chip: select it at target centroid then X
            c0 = wpt(tx, ty)
            pyautogui.click(c0[0], c0[1])
            time.sleep(0.9)
            matrix = board_matrix(grab())
            if cells_filled(matrix, target):
                # selection worked, X is below-right of the chip centroid
                pyautogui.click(c0[0] + 90, c0[1] + 130)
                time.sleep(0.9)
            print(f"[{chip}] attempt {attempt} failed, deleted if possible", flush=True)
        if not placed:
            print(f"[{chip}] GIVING UP", flush=True)
            print(json.dumps({"results": [{k: v["ok"] if isinstance(v, dict) else v for k, v in []}]}))
            print(json.dumps({"done": list(done.keys()), "failed": chip}, ensure_ascii=False), flush=True)
            return
        done[chip] = True
        # deselect via the single free cell
        fx, fy = wpt(*FREE_CELL)
        pyautogui.click(fx, fy)
        time.sleep(0.6)
    # final board dump
    matrix = board_matrix(grab())
    print("FINAL BOARD:")
    for line in matrix:
        print("   ", " ".join(line), flush=True)
    print(json.dumps({"done": list(done.keys())}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
