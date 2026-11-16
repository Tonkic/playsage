import sys
import time

import pyautogui
from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False

# select slot1 (P pentomino 领主) then click target cells centroid (742,417 window-rel)
sx, sy = 1432 + 8, 345 + 31
pyautogui.moveTo(sx, sy)
time.sleep(0.4)
pyautogui.click()
time.sleep(1.2)
tx, ty = 742 + 8, 417 + 31
pyautogui.moveTo(tx, ty)
time.sleep(0.4)
pyautogui.click()
time.sleep(1.5)
img = ImageGrab.grab().convert("RGB")
img.save(r"D:\PlaySage\runs\observations\sra\s2_clickplace.png")
print("done")
