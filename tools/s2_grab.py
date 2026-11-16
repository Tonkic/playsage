import sys
import time

import pyautogui
from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False
img = ImageGrab.grab()
print("grab size:", img.size)
img.save(r"D:\PlaySage\runs\observations\sra\s2_full.png")
# sample some pixels
for pt in ((960, 540), (1440, 376), (100, 100)):
    print(pt, img.getpixel(pt))
