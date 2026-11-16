import ctypes
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
user32 = ctypes.windll.user32


class PT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


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
print("candidates:", [hex(h) for h in found], flush=True)
hwnd = found[0]

pt = PT(0, 0)
user32.ClientToScreen(hwnd, ctypes.byref(pt))
print("current client origin:", pt.x, pt.y, flush=True)
rect = RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
print("window rect:", rect.left, rect.top, rect.right, rect.bottom, flush=True)

# target client origin (8, 31): shift the window by the delta
dx = 8 - pt.x
dy = 31 - pt.y
user32.SetWindowPos(hwnd, 0, rect.left + dx, rect.top + dy,
                    rect.right - rect.left, rect.bottom - rect.top, 0x0004)
time.sleep(0.8)
user32.ClientToScreen(hwnd, ctypes.byref(pt))
print("client origin after move:", pt.x, pt.y, flush=True)
