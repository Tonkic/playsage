"""PostMessage-based background input for Honkai: Star Rail.

Window-message input does not require window focus, unlike cursor-based
SendInput injection. Coordinates are 1080p client pixels.
"""
import argparse
import ctypes
import time

user32 = ctypes.windll.user32
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001


def find_window():
    hwnd = user32.FindWindowW("UnityWndClass", "崩坏：星穹铁道")
    if not hwnd:
        hwnd = user32.FindWindowW(None, "崩坏：星穹铁道")
    return hwnd


def makelparam(x, y):
    return (y << 16) | (x & 0xFFFF)


def click(x, y):
    hwnd = find_window()
    lp = makelparam(x, y)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.08)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)


def key(vk):
    hwnd = find_window()
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    time.sleep(0.06)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)


VK = {"esc": 0x1B, "enter": 0x0D, "space": 0x20, "f": 0x46, "e": 0x45, "q": 0x51,
      "v": 0x56, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34, "m": 0x4D, "r": 0x52}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["click", "key", "hwnd"])
    parser.add_argument("--x", type=int)
    parser.add_argument("--y", type=int)
    parser.add_argument("--key")
    a = parser.parse_args()
    if a.action == "hwnd":
        print(find_window())
    elif a.action == "click":
        click(a.x, a.y)
        print(f"clicked {a.x},{a.y}")
    else:
        key(VK[a.key])
        print(f"key {a.key}")
