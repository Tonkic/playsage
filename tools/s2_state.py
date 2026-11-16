import sys
import time

import pyautogui
from PIL import ImageGrab

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False
img = ImageGrab.grab().convert("RGB")
img.save(r"D:\PlaySage\runs\observations\sra\s2_state.png")
print("saved", img.size)
