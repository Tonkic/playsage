import sys
import time

import pyautogui
from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False

# scroll the chip list (right panel) down: wheel at (1650, 600) screen
lx, ly = 1650 + 8, 600 + 31
pyautogui.moveTo(lx, ly)
time.sleep(0.4)
for _ in range(6):
    pyautogui.scroll(-5)
    time.sleep(0.3)
time.sleep(1.0)
img = ImageGrab.grab().convert("RGB")
img.save(r"D:\PlaySage\runs\observations\sra\s2_scrolled.png")
print("scrolled + saved")
