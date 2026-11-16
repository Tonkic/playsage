import json
import sys
import time

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8")
import httpio

# fullscreen grid: origin (682,292), cell (80.4, 77.7) — screen 1080p px
def drop(c, r):
    return (int(682 + 80.4 * (c + 0.5)), int(292 + 77.7 * (r + 0.5)))

# slots in SRA space (client - 8,31): s1=(1424,531), s2=(1664,531), s3=(1424,749)
CHIPS = [
    ("s1_hmz2", 1424, 531, (6, 2), [(6,2),(6,3)]),      # 毁灭者 domino vertical
    ("s2_xf2",  1664, 531, (5, 3), [(5,3),(5,4)]),      # 先锋 domino vertical
    ("s3_ds2",  1424, 749, (4, 3), [(4,3),(4,4),(4,5),(5,5)]),  # 斗士 L
]


def main():
    for chip, sx, sy, anchor, cells in CHIPS:
        tc = (sum(p[0] for p in cells) / len(cells), sum(p[1] for p in cells) / len(cells))
        tx, ty = drop(*[int(v) for v in anchor])
        # drop at anchor cell center
        r = httpio.op("drag_to", from_x=sx - 8, from_y=sy - 31, to_x=tx, to_y=ty, duration=1.5)
        print(f"[{chip}] {r}", flush=True)
        time.sleep(0.9)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
