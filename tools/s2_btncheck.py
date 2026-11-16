import ctypes
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
user32 = ctypes.windll.user32
VK_LBUTTON = 0x01

st = user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000
print("left button DOWN?" , bool(st), flush=True)

# force release then check
pyautogui = __import__("pyautogui")
pyautogui.FAILSAFE = False
pyautogui.mouseUp(button="left")
time.sleep(0.3)
st2 = user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000
print("after force release:", bool(st2), flush=True)
