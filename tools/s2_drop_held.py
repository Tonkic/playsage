import sys
import time

import pyautogui

sys.stdout.reconfigure(encoding="utf-8")
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# the held grey domino: cursor should be near screen (1156,442)
# move it to the valid vertical spot col6 rows2-3: screen (1205,525)
print("moveTo held pos", flush=True)
pyautogui.moveTo(1156, 442)
time.sleep(0.4)
print("moveTo valid drop (1205,525)", flush=True)
pyautogui.moveTo(1205, 525, duration=0.6)
time.sleep(0.4)
print("mouseUp (drop chip)", flush=True)
pyautogui.mouseUp()
time.sleep(1.2)
print("pos:", pyautogui.position(), flush=True)
print("DONE - chip should be dropped legally", flush=True)
