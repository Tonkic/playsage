"""Full mecha-order flow via PostMessage background input (cross-session)."""
import ctypes
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
user32 = ctypes.windll.user32

WM_ACTIVATE = 0x0006
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
WA_ACTIVE = 1
VK_F = 0x46


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


def lp(x, y, down):
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def post(hwnd, msg, w, l):
    user32.PostMessageW(hwnd, msg, w, l)


def activate(hwnd):
    post(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    time.sleep(0.05)


def click(hwnd, x, y, pause=0.6):
    activate(hwnd)
    post(hwnd, WM_MOUSEMOVE, 0, lp(x, y, False))
    time.sleep(0.08)
    post(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp(x, y, True))
    time.sleep(0.1)
    post(hwnd, WM_MOUSEMOVE, MK_LBUTTON, lp(x, y, True))
    time.sleep(0.08)
    post(hwnd, WM_LBUTTONUP, 0, lp(x, y, False))
    time.sleep(pause)


def key(hwnd, vk, pause=0.8):
    activate(hwnd)
    post(hwnd, WM_KEYDOWN, vk, 0)
    time.sleep(0.12)
    post(hwnd, WM_KEYUP, 0, 0)
    time.sleep(pause)


def drag(hwnd, start, end, duration=0.6):
    activate(hwnd)
    sx, sy = start
    ex, ey = end
    steps = max(8, min(30, int(((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5 / 12)))
    post(hwnd, WM_MOUSEMOVE, 0, lp(sx, sy, False))
    time.sleep(0.06)
    post(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp(sx, sy, True))
    time.sleep(0.1)
    started = time.monotonic()
    for i in range(1, steps + 1):
        ix = sx + (ex - sx) * i / steps
        iy = sy + (ey - sy) * i / steps
        post(hwnd, WM_MOUSEMOVE, MK_LBUTTON, lp(int(ix), int(iy), True))
        tt = started + duration * i / steps
        while time.monotonic() < tt:
            time.sleep(0.004)
    time.sleep(0.12)
    post(hwnd, WM_LBUTTONUP, 0, lp(ex, ey, False))
    time.sleep(0.5)


def main():
    hwnd = find_game()
    if not hwnd:
        print("GAME WINDOW NOT FOUND", flush=True)
        return
    print("hwnd:", hex(hwnd), flush=True)

    # the game is at the workshop (开始设计机铠 prompt was visible)
    # 1. open orders: click 查看订单 (client 1523,848)
    click(hwnd, 1523, 848, pause=2.5)
    # 2. click 马上开工 (1586,996)
    click(hwnd, 1586, 996, pause=2.5)
    # 3. click 确认 on splash (956,887)
    click(hwnd, 956, 887, pause=3)
    print("puzzle opened, placing chips...", flush=True)

    # 4. five placements: slot (client) -> drop (client cell center)
    placements = [
        ((1432, 345), (710, 315)),   # s1 毁灭者 Z -> (0,0)-(2,1)
        ((1680, 345), (948, 315)),   # s2 先锋 O -> (3,0)-(4,1)
        ((1432, 562), (1107, 315)),  # s3 斗士 L -> (5,0)-(6,2)
        ((1432, 780), (710, 484)),   # s5 先锋 domino -> (0,2)-(1,2)
        ((1680, 780), (869, 484)),   # s6 毁灭者 domino -> (2,2)-(2,3)
    ]
    for (sx, sy), (tx, ty) in placements:
        drag(hwnd, (sx, sy), (tx, ty), duration=0.8)
        print(f"placed ({tx},{ty})", flush=True)
        time.sleep(0.3)

    # 5. deselect + 完成设计 (956,887)
    click(hwnd, 1044, 315, pause=0.5)
    click(hwnd, 956, 887, pause=2.0)
    click(hwnd, 1174, 641, pause=2.0)  # confirm dialog
    print("SUBMITTED", flush=True)


if __name__ == "__main__":
    main()
