import sys
import time

import pyautogui
from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False

sx, sy = 1432 + 8, 345 + 31
pyautogui.moveTo(sx, sy)
time.sleep(0.4)
pyautogui.click()
time.sleep(1.2)
img = ImageGrab.grab().convert("RGB")
img.save(r"D:\PlaySage\runs\observations\sra\s2_sel_test.png")
# sample the slot border area for the white selection ring
print("saved full grab")
