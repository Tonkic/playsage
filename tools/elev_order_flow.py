"""Elevated M7A-style input: SetCursorPos + SendMessageTimeout drag, full order flow."""
import ctypes
import ctypes.wintypes as wt
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
SMTO_BLOCK = 0x0001
TIMEOUT_MS = 800


class PT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def find_game():
    found = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if "星穹铁道" in buf.value:
                found.append(hwnd)
        return True

    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(CB(cb), None)
    return found[0] if found else None


def client_to_screen(hwnd, x, y):
    pt = PT(int(x), int(y))
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def lparam(x, y):
    return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)


def send(hwnd, msg, w, l):
    res = ctypes.c_size_t()
    user32.SendMessageTimeoutW(hwnd, msg, w, l, SMTO_BLOCK, TIMEOUT_MS, ctypes.byref(res))


def activate(hwnd):
    user32.PostMessageW(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    time.sleep(0.05)


def move_cursor(hwnd, cx, cy):
    sx, sy = client_to_screen(hwnd, cx, cy)
    user32.SetCursorPos(sx, sy)
    send(hwnd, WM_MOUSEMOVE, 0, lparam(int(cx), int(cy)))


def click(hwnd, cx, cy, pause=1.2):
    activate(hwnd)
    move_cursor(hwnd, cx, cy)
    time.sleep(0.1)
    send(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam(cx, cy))
    time.sleep(0.12)
    send(hwnd, WM_LBUTTONUP, 0, lparam(cx, cy))
    time.sleep(pause)


def drag(hwnd, start, end, duration=0.8):
    activate(hwnd)
    sx, sy = start
    ex, ey = end
    move_cursor(hwnd, sx, sy)
    time.sleep(0.1)
    send(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam(sx, sy))
    time.sleep(0.15)
    steps = max(10, min(40, int(((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5 / 10)))
    started = time.monotonic()
    for i in range(1, steps + 1):
        ix = sx + (ex - sx) * i / steps
        iy = sy + (ey - sy) * i / steps
        move_cursor(hwnd, ix, iy)
        tt = started + duration * i / steps
        while time.monotonic() < tt:
            time.sleep(0.003)
    time.sleep(0.12)
    send(hwnd, WM_LBUTTONUP, 0, lparam(ex, ey))
    time.sleep(0.5)


def main():
    hwnd = find_game()
    print("hwnd:", hex(hwnd) if hwnd else None, flush=True)
    if not hwnd:
        sys.exit(1)

    origin = client_to_screen(hwnd, 0, 0)
    print("client origin:", origin, flush=True)

    # flow: orders -> puzzle -> chips -> submit (client coords)
    click(hwnd, 1523, 848, pause=2.5)   # 查看订单
    click(hwnd, 1586, 996, pause=2.5)   # 马上开工
    click(hwnd, 956, 887, pause=3)      # 确认 splash
    print("puzzle open", flush=True)

    placements = [
        ((1432, 345), (710, 315)),   # 毁灭者 Z
        ((1680, 345), (948, 315)),   # 先锋 O
        ((1432, 562), (1107, 315)),  # 斗士 L
        ((1432, 780), (710, 484)),   # 先锋 domino
        ((1680, 780), (869, 484)),   # 毁灭者 domino
    ]
    for (sx, sy), (tx, ty) in placements:
        drag(hwnd, (sx, sy), (tx, ty), duration=1.0)
        print(f"placed ({tx},{ty})", flush=True)
        time.sleep(0.3)

    click(hwnd, 1044, 315, pause=0.6)   # deselect
    click(hwnd, 956, 887, pause=2.5)    # 完成设计
    click(hwnd, 1174, 641, pause=2.5)   # confirm dialog
    print("SUBMITTED", flush=True)


if __name__ == "__main__":
    main()
