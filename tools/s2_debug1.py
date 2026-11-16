import sys
import time

import pyautogui
from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False
OUT = r"D:\PlaySage\runs\observations\sra"

import ctypes


def game_client_origin():
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "崩坏：星穹铁道")
    class PT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = PT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


WL, WT = game_client_origin()
GX0, GY0, GW, GH = 670.5, 273.0, 79.3, 84.5
print("origin:", WL, WT, flush=True)

img = ImageGrab.grab().convert("RGB")
img.save(OUT + r"\st_0_start.png")

# 1. click slot1 (P pentomino 领主)
pyautogui.click(WL + 1432, WT + 345)
time.sleep(1.2)
ImageGrab.grab().convert("RGB").save(OUT + r"\st_1_selected.png")

# 2. slow drag to the P target centroid (0.4,1.2) -> (750.4, 434.1) client
tx = WL + GX0 + GW * 0.9
ty = WT + GY0 + GH * 1.7
pyautogui.moveTo(WL + 1432, WT + 345)
time.sleep(0.3)
pyautogui.mouseDown()
time.sleep(0.3)
cx, cy = pyautogui.position()
for i in range(1, 25):
    pyautogui.moveTo(cx + (tx - cx) * i / 24, cy + (ty - cy) * i / 24)
    time.sleep(0.05)
time.sleep(0.5)
img = ImageGrab.grab().convert("RGB")
img.save(OUT + r"\st_2_midhold.png")
print("mid pos:", pyautogui.position(), flush=True)

# 3. release
pyautogui.mouseUp()
time.sleep(1.2)
ImageGrab.grab().convert("RGB").save(OUT + r"\st_3_dropped.png")
print("done", flush=True)
