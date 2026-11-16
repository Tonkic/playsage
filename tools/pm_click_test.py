import ctypes
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
user32 = ctypes.windll.user32

WM_ACTIVATE = 0x0006
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
WA_ACTIVE = 1


def find_game():
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if "星穹铁道" in buf.value:
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, None)
    return found[0] if found else None


def lp(x, y):
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


hwnd = find_game()
print("hwnd:", hex(hwnd), flush=True)
if not hwnd:
    sys.exit(1)

# activate
user32.PostMessageW(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
time.sleep(0.3)
# extra move events to wake the input
for _ in range(3):
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp(1000, 500))
    time.sleep(0.05)
# click 查看订单 at client (1523,848)
user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp(1523, 848))
time.sleep(0.1)
user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp(1523, 848))
time.sleep(0.15)
for _ in range(3):
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, MK_LBUTTON, lp(1523, 848))
    time.sleep(0.03)
user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp(1523, 848))
print("click posted", flush=True)
