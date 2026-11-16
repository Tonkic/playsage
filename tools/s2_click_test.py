import sys
import time

import pyautogui
from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False

# click slot1 (window-rel 1432,345 -> screen +8,+31)
sx, sy = 1432 + 8, 345 + 31
pyautogui.moveTo(sx, sy)
time.sleep(0.4)
pyautogui.click()
time.sleep(1.5)
img = ImageGrab.grab().convert("RGB")
img.crop((int(sx * img.width / 1920) - 150, int(sy * img.height / 1080) - 150,
          int(sx * img.width / 1920) + 150, int(sy * img.height / 1080) + 150)
         ).save(r"D:\PlaySage\runs\observations\sra\s2_click_crop.png")
print("clicked, crop saved")
