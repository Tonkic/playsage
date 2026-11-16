import ctypes
import sys

sys.stdout.reconfigure(encoding="utf-8")
user32 = ctypes.windll.user32


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


result = []


@ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
def cb(hwnd, _):
    if not user32.IsWindowVisible(hwnd):
        return True
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    # any window covering most of the screen
    if w >= 1800 and h >= 1000:
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        # extended style: transparent / layered / toolwindow
        ex = user32.GetWindowLongW(hwnd, -20)
        result.append((hex(hwnd), buf.value[:30], cls.value[:40], w, h, hex(ex)))
    return True


user32.EnumWindows(cb, None)
for r in result:
    print(r, flush=True)
print("total:", len(result), flush=True)
