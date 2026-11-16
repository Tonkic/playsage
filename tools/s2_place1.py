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

def ghost_cells(img, color="p"):
    sx = img.width / 1920.0
    sy = img.height / 1080.0
    found = set()
    for r in range(6):
        for c in range(7):
            wx, wy = WL + GX0 + GW * (c + 0.5), WT + GY0 + GH * (r + 0.5)
            x, y = int(wx * sx), int(wy * sy)
            rr, gg, bb = img.getpixel((x, y))
            if rr > 195 and 125 < gg < 182 and 160 < bb < 215:
                found.add((c, r))
    return found

def norm(cells):
    mx = min(c for c, r in cells); my = min(r for c, r in cells)
    return sorted((c - mx, r - my) for c, r in cells)

TARGET = [(0, 0), (0, 1), (0, 2), (1, 1), (1, 2)]
tx = sum(p[0] for p in TARGET) / 5; ty = sum(p[1] for p in TARGET) / 5
tpx = WL + GX0 + GW * (tx + 0.5); tpy = WT + GY0 + GH * (ty + 0.5)

# focus
pyautogui.moveTo(WL + 960, WT + 540)
time.sleep(0.3)
pyautogui.click()
time.sleep(0.8)

# grab from slot1 and drag slowly to target
pyautogui.moveTo(WL + 1432, WT + 345)
time.sleep(0.4)
pyautogui.mouseDown()
time.sleep(0.35)
cx, cy = pyautogui.position()
for i in range(1, 25):
    pyautogui.moveTo(cx + (tpx - cx) * i / 24, cy + (tpy - cy) * i / 24)
    time.sleep(0.06)
time.sleep(0.6)

img = grab()
g = ghost_cells(img)
print("ghost after drag:", sorted(g))
if not (g and norm(g) == norm(TARGET)):
    for a in range(4):
        pyautogui.press("r")
        time.sleep(0.5)
        img = grab()
        g = ghost_cells(img)
        print(f"  after R{a+1}:", sorted(g))
        if g and norm(g) == norm(TARGET):
            break
if g and norm(g) == norm(TARGET):
    # fine shift
    gcx = sum(p[0] for p in g) / len(g); gcy = sum(p[1] for p in g) / len(g)
    dc = (tx - gcx) * GW; dr = (ty - gcy) * GH
    cx, cy = pyautogui.position()
    for i in range(1, 7):
        pyautogui.moveTo(cx + dc * i / 6, cy + dr * i / 6)
        time.sleep(0.04)
    time.sleep(0.4)
    pyautogui.mouseUp()
    time.sleep(1.2)
    img = grab()
    g2 = ghost_cells(img)
    print("after drop ghost:", sorted(g2))
else:
    print("ABORT drag - no valid ghost, releasing over inventory")
    pyautogui.moveTo(WL + 1432, WT + 345)
    time.sleep(0.3)
    pyautogui.mouseUp()
img.save(r"D:\PlaySage\runs\observations\sra\s2_place1.png")
