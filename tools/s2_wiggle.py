import ctypes
import json
import sys
import time

import pyautogui
from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False

user32 = ctypes.windll.user32


class PT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def game_hwnd():
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if "星穹铁道" in buf.value:
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, None)
    return found[0] if found else None


hwnd = game_hwnd()
print("hwnd:", hex(hwnd), flush=True)

# restore window to (0,0) so client origin = (8,31)
rect = ctypes.wintypes.RECT() if hasattr(ctypes, "wintypes") else None
import ctypes.wintypes as wt
rect = wt.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
print("window rect before:", rect.left, rect.top, flush=True)
user32.SetWindowPos(hwnd, 0, 0, 0, rect.right - rect.left, rect.bottom - rect.top, 0x0004)
time.sleep(0.6)
pt = PT(0, 0)
user32.ClientToScreen(hwnd, ctypes.byref(pt))
print("client origin now:", pt.x, pt.y, flush=True)
WL, WT = pt.x, pt.y

GX0, GY0, GW, GH = 670.5, 273.0, 79.3, 84.5


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
            rr, gg, bb = img.getpixel((x, y))
            if rr > 200 and 150 < gg < 220 and 150 < bb < 220: k = "P"
            elif bb > 200 and 150 < gg < 230 and 100 < rr < 180: k = "B"
            elif rr < 75 and gg < 80 and bb < 95: k = "."
            else: k = "?"
            line.append(k)
        out.append(line)
    return out


# THE DRAG: click-activate the game first, then press INSIDE the slot, wiggle
# within the slot for a while (let the game register the press), then ease out
pyautogui.click(WL + 400, WT + 150)  # harmless activate click
time.sleep(0.7)

slot = (WL + 1432, WT + 345)
tx = WL + GX0 + GW * 0.9   # target centroid (0.4,1.2) of the P shape
ty = WT + GY0 + GH * 1.7

pyautogui.moveTo(slot[0], slot[1])
time.sleep(0.3)
pyautogui.mouseDown()
# wiggle inside the slot for 0.5s (game registers press on the chip)
for dx, dy in ((2, 0), (-2, 1), (3, -1), (0, 2)):
    pyautogui.moveTo(slot[0] + dx, slot[1] + dy)
    time.sleep(0.12)
# ease out toward target: slow first, then faster
for i in range(1, 41):
    t = i / 40.0
    ease = t * t * (3 - 2 * t)  # smoothstep
    pyautogui.moveTo(slot[0] + (tx - slot[0]) * ease, slot[1] + (ty - slot[1]) * ease)
    time.sleep(0.045)
time.sleep(0.5)
img = grab()
img.save(r"D:\PlaySage\runs\observations\sra\wiggle_mid.png")
pyautogui.mouseUp()
time.sleep(1.3)
img = grab()
img.save(r"D:\PlaySage\runs\observations\sra\wiggle_done.png")
m = board_matrix(img)
for line in m:
    print(" ".join(line), flush=True)
print("done", flush=True)
