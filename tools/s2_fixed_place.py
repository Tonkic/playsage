import sys
import time

import pyautogui
from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False
WL, WT = 8, 31
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


# 1. ACTIVATE the game window with a harmless click (top-left empty corner area)
pyautogui.click(WL + 200, WT + 150)
time.sleep(0.8)

# 2. verify activation: selection should work now — click slot1 (selects it)
pyautogui.click(WL + 1432, WT + 345)
time.sleep(1.0)

# 3. drag the selected chip out: down, SLOW move, up
tx = WL + GX0 + GW * 0.9
ty = WT + GY0 + GH * 1.7
pyautogui.moveTo(WL + 1432, WT + 345)
time.sleep(0.3)
pyautogui.mouseDown()
time.sleep(0.35)
cx, cy = pyautogui.position()
for i in range(1, 25):
    pyautogui.moveTo(cx + (tx - cx) * i / 24, cy + (ty - cy) * i / 24)
    time.sleep(0.05)
time.sleep(0.5)
pyautogui.mouseUp()
time.sleep(1.2)

img = grab()
img.save(r"D:\PlaySage\runs\observations\sra\s2_fixed_place.png")
m = board_matrix(img)
for line in m:
    print(" ".join(line), flush=True)
