import pyautogui
import time
import sys

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False
print("screen size:", pyautogui.size())
pyautogui.moveTo(960, 540)
time.sleep(0.3)
print("pos:", pyautogui.position())
