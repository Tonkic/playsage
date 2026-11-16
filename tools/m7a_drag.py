"""M7A-style background drag for HSR via PostMessage (no focus, no elevation)."""
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


def lparam(x, y, down):
    # lparam: high word = flags (0 release / MK_LBUTTON press), low word = y<<16|x
    flags = 1 if down else 0
    return (flags << 16) | ((y & 0xFFFF) << 16) | (x & 0xFFFF) if False else (y & 0xFFFF) << 16 | (x & 0xFFFF)


def post(hwnd, msg, w, l):
    user32.PostMessageW(hwnd, msg, w, l)


def drag(hwnd, start, end, duration=0.6, steps=None):
    """Interpolated drag via posted messages (client coords)."""
    sx, sy = start
    ex, ey = end
    if steps is None:
        steps = max(6, min(24, int(((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5 / 16)))
    # activate
    post(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    time.sleep(0.05)
    # move to start
    post(hwnd, WM_MOUSEMOVE, 0, lparam(sx, sy, False))
    time.sleep(0.05)
    # press
    post(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam(sx, sy, True))
    time.sleep(0.08)
    # interpolated moves
    started = time.monotonic()
    for i in range(1, steps + 1):
        ix = sx + (ex - sx) * i / steps
        iy = sy + (ey - sy) * i / steps
        post(hwnd, WM_MOUSEMOVE, MK_LBUTTON, lparam(int(ix), int(iy), True))
        # pacing like M7A (~0.1s per 6 steps)
        target_t = started + duration * i / steps
        while time.monotonic() < target_t:
            time.sleep(0.005)
    time.sleep(0.1)
    # release at end
    post(hwnd, WM_LBUTTONUP, 0, lparam(ex, ey, False))
    time.sleep(0.15)


if __name__ == "__main__":
    hwnd = find_game()
    print("hwnd:", hex(hwnd), flush=True)
    if not hwnd:
        sys.exit(1)
    # test drag: slot1 chip (1432,345) -> (742,417) — client coords (fullscreen = client == screen)
    drag(hwnd, (1432, 345), (742, 417), duration=0.6)
    print("drag done", flush=True)
