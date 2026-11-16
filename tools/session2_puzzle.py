"""Session-2 standalone puzzle driver: runs as a scheduled task inside the
child session, drives the game with pyautogui directly (no MCP dependency).

Usage: session2_puzzle.py '<steps-json>'
Step: {"chip": name, "slot": [x,y], "cells": [[c,r],...], "color": "p"|"b",
       "tab": [x,y]|null, "rot": 0-3}
Coordinates: 1080p window-relative (window origin added internally).
"""
import io
import json
import sys
import time

import pyautogui
from PIL import ImageGrab

pyautogui.FAILSAFE = False
WIN_LEFT, WIN_TOP = 8, 31
GW, GH = 79.3, 84.5
GX0, GY0 = 670.5, 273.0


def cell_center(c, r):
    return (WIN_LEFT + GX0 + GW * (c + 0.5), WIN_TOP + GY0 + GH * (r + 0.5))


def cells_centroid(cells):
    cs = [p[0] for p in cells]; rs = [p[1] for p in cells]
    return (sum(cs) / len(cs), sum(rs) / len(rs))


def grab():
    img = ImageGrab.grab()
    return img.convert("RGB")


def norm(cells):
    mx = min(c for c, r in cells); my = min(r for c, r in cells)
    return sorted((c - mx, r - my) for c, r in cells)


def ghost_cells(img, color):
    sx = img.width / 1920.0
    sy = img.height / 1080.0
    found = set()
    for r in range(6):
        for c in range(7):
            wx, wy = cell_center(c, r)
            x, y = int(wx * sx), int(wy * sy)
            if x >= img.width or y >= img.height:
                continue
            rr, gg, bb = img.getpixel((x, y))
            if color == "p" and rr > 195 and 125 < gg < 182 and 160 < bb < 215:
                found.add((c, r))
            if color == "b" and 80 < rr < 125 and 140 < gg < 185 and 195 < bb < 235:
                found.add((c, r))
    return found


def revive():
    pyautogui.moveTo(int(WIN_LEFT + 960), int(WIN_TOP + 540))
    time.sleep(0.25)


def main(steps):
    pyautogui.FAILSAFE = False
    results = []
    for st in steps:
        chip = st["chip"]
        color = st["color"]
        target = [tuple(c) for c in st["cells"]]
        try:
            if st.get("tab"):
                tx, ty = st["tab"]
                pyautogui.click(WIN_LEFT + tx, WIN_TOP + ty)
                time.sleep(1.2)
            revive()
            sx, sy = st["slot"]
            # engage drag with slow interpolated move toward the target centroid
            tx, ty = cells_centroid(target)
            tpx = WIN_LEFT + GX0 + GW * (tx + 0.5)
            tpy = WIN_TOP + GY0 + GH * (ty + 0.5)
            pyautogui.moveTo(WIN_LEFT + sx, WIN_TOP + sy)
            time.sleep(0.3)
            pyautogui.mouseDown(button="left")
            time.sleep(0.35)
            steps_n = 18
            cx, cy = pyautogui.position()
            for i in range(1, steps_n + 1):
                nx = cx + (tpx - cx) * i / steps_n
                ny = cy + (tpy - cy) * i / steps_n
                pyautogui.moveTo(nx, ny)
                time.sleep(0.05)
            time.sleep(0.5)

            # rotation loop: match ghost shape to target
            ok = False
            for attempt in range(5):
                img = grab()
                ghost = ghost_cells(img, color)
                if ghost and norm(ghost) == norm(target):
                    ok = True
                    print(f"[{chip}] ghost matched after {attempt} rotations", flush=True)
                    break
                pyautogui.press("r")
                time.sleep(0.5)
            if not ok:
                img = grab()
                print(f"[{chip}] NO MATCH ghost={sorted(ghost_cells(img, color))} -- abort step", flush=True)
                # release over the grid corner empty area to avoid stray drops
                pyautogui.moveTo(WIN_LEFT + 700, WIN_TOP + 250)
                time.sleep(0.3)
                pyautogui.mouseUp(button="left")
                time.sleep(0.6)
                results.append({"chip": chip, "ok": False})
                continue

            # fine shift by centroid delta
            img = grab()
            ghost = ghost_cells(img, color)
            gcx = sum(p[0] for p in ghost) / len(ghost)
            gcy = sum(p[1] for p in ghost) / len(ghost)
            dc = (tx - gcx) * GW
            dr = (ty - gcy) * GH
            cx, cy = pyautogui.position()
            px, py = cx + dc, cy + dr
            for i in range(1, 7):
                pyautogui.moveTo(cx + (px - cx) * i / 6, cy + (py - cy) * i / 6)
                time.sleep(0.03)
            time.sleep(0.4)
            img = grab()
            ghost = ghost_cells(img, color)
            if not ghost or norm(ghost) != norm(target):
                print(f"[{chip}] ghost mismatch after shift: {sorted(ghost)}", flush=True)
                pyautogui.moveTo(WIN_LEFT + 700, WIN_TOP + 250)
                time.sleep(0.3)
                pyautogui.mouseUp(button="left")
                time.sleep(0.6)
                results.append({"chip": chip, "ok": False})
                continue
            pyautogui.mouseUp(button="left")
            time.sleep(1.0)
            print(f"[{chip}] DROPPED", flush=True)
            results.append({"chip": chip, "ok": True})
        except Exception as e:
            print(f"[{chip}] ERROR {e}", flush=True)
            try:
                pyautogui.mouseUp(button="left")
            except Exception:
                pass
            results.append({"chip": chip, "ok": False, "error": str(e)})
    print(json.dumps({"results": results}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(json.loads(sys.argv[1]))
