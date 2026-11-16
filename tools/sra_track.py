"""Screen-center quest marker tracking for HSR via the SRA REST API (v3).

UI state is classified per frame by OCR:
- dialog: text in the bottom strip -> press Enter to advance
- menu: menu keywords in the right half -> press ESC to close
- otherwise in world: steer the camera so the gold quest marker is centered,
  walk W while centered, press F when the marker is very low (close).
"""
import io
import json
import sys
import time
from urllib.request import Request, urlopen

from PIL import Image

BASE = "http://127.0.0.1:5000"
CENTER_X, CENTER_Y = 640, 330
EVIDENCE = r"D:\PlaySage\runs\observations\sra"
MENU_WORDS = ("商店", "好友", "委托", "编队", "背包", "任务", "指南", "跃迁", "短信")


def api(path, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(BASE + path, data=data, method="POST" if data else "GET",
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def op(method, params=None):
    r = api("/api/operator/call", {"method": method, "params": params or {}})
    return r.get("success", False)


def frame():
    with urlopen(BASE + "/api/backend/screenshot", timeout=30) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def find_gold_marker(img):
    w, h = img.size
    px = img.load()
    xs, ys = [], []
    for y in range(40, int(h * 0.72), 4):
        for x in range(170, w - 260, 4):
            if 500 < x < 780 and 420 < y < h:  # exclude the player character
                continue
            r, g, b = px[x, y]
            if r > 205 and 120 < g < 230 and b < 130 and r - b > 100:
                xs.append(x)
                ys.append(y)
    if len(xs) < 4:
        return None
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    cluster = [(x, y) for x, y in zip(xs, ys) if abs(x - cx) < 120 and abs(y - cy) < 90]
    if len(cluster) < 4:
        return None
    return (sum(p[0] for p in cluster) / len(cluster),
            sum(p[1] for p in cluster) / len(cluster))


def ocr_items(fx0, fy0, fx1, fy1):
    r = api("/api/operator/call", {"method": "ocr",
        "params": {"fromX": fx0, "fromY": fy0, "toX": fx1, "toY": fy1}})
    data = r.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return []
    if isinstance(data, dict):
        data = data.get("result", [])
    out = []
    for it in data or []:
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            out.append(str(it[1]))
    return out


def rotate(dx_px):
    op("mouse_down", {"x": 640, "y": 380, "button": "right"})
    time.sleep(0.1)
    steps = 4
    per = max(-100, min(100, dx_px / 3.5)) / steps
    for _ in range(steps):
        op("move_rel", {"x_offset": int(per), "y_offset": 0})
        time.sleep(0.05)
    op("mouse_up", {"button": "right"})


def classify(items_bottom, items_right):
    bottom = " ".join(items_bottom)
    right = " ".join(items_right)
    if len(bottom.strip()) >= 6:
        return "dialog", bottom
    if any(w in right for w in MENU_WORDS):
        return "menu", right
    return "world", right


def main(max_iters=50):
    last_dx = 60
    lost_streak = 0
    for i in range(max_iters):
        img = frame()
        if i % 10 == 0:
            img.save(fr"{EVIDENCE}\track3_{i:03d}.jpg", quality=80)
        bottom = ocr_items(0.18, 0.72, 0.82, 0.96)
        right = ocr_items(0.62, 0.15, 0.99, 0.85)
        state, text = classify(bottom, right)
        if state == "dialog":
            op("press_key", {"key": "enter"})
            time.sleep(0.5)
            print(f"[{i}] dialog: {bottom[0][:40]}")
            continue
        if state == "menu":
            op("press_key", {"key": "esc"})
            time.sleep(0.6)
            print(f"[{i}] menu -> esc")
            continue
        marker = find_gold_marker(img)
        if marker is None:
            lost_streak += 1
            if lost_streak % 3 == 0:
                op("hold_key", {"key": "w", "duration": 0.9})
            else:
                rotate(last_dx)
            print(f"[{i}] marker lost ({lost_streak}) rotate {last_dx:+d}")
            time.sleep(0.4)
            continue
        lost_streak = 0
        dx = marker[0] - CENTER_X
        dy = marker[1] - CENTER_Y
        last_dx = 120 if dx >= 0 else -120
        print(f"[{i}] marker ({marker[0]:.0f},{marker[1]:.0f}) dx={dx:.0f} dy={dy:.0f}")
        if abs(dx) > 190:
            rotate(dx)
            time.sleep(0.35)
        elif dy > 195:
            op("press_key", {"key": "f"})
            time.sleep(1.4)
            print(f"[{i}] pressed F (marker low)")
        else:
            op("hold_key", {"key": "w", "duration": 1.1})
            time.sleep(0.25)
    img = frame()
    img.save(fr"{EVIDENCE}\track3_final.jpg", quality=85)
    items = ocr_items(0.02, 0.24, 0.30, 0.40)
    print("final tracker:", " ".join(items)[:220])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 50)
