import ctypes
import sys

sys.stdout.reconfigure(encoding="utf-8")
user32 = ctypes.windll.user32
fg = user32.GetForegroundWindow()
buf = ctypes.create_unicode_buffer(256)
user32.GetWindowTextW(fg, buf, 256)
print("foreground hwnd:", hex(fg), "title:", repr(buf.value))
# list ALL visible top-level windows with titles
result = []


@ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
def cb(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        b = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, b, 256)
        if b.value.strip():
            result.append((hex(hwnd), b.value[:40]))
    return True


user32.EnumWindows(cb, None)
for h, t in result[:15]:
    print(h, t)
