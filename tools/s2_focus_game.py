import ctypes
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
user32 = ctypes.windll.user32
SW_RESTORE = 9


def find_game():
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if "星穹铁道" in buf.value:
            out.append(hwnd)
        return True

    user32.EnumWindows(cb, None)
    return out


wins = find_game()
print("windows:", [hex(h) for h in wins])
for hwnd in wins:
    print(f"  {hex(hwnd)} iconic={user32.IsIconic(hwnd)} visible={user32.IsWindowVisible(hwnd)}")
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.6)
    # force topmost then foreground
    ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
    time.sleep(0.2)
    ctypes.windll.user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    print("  foreground:", user32.GetForegroundWindow() == hwnd)
