import json
import sys
import time

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8")
import httpio

# remaining 3 chips: s1 (毁灭者#2), s2 (先锋#2), s3 (斗士#2)
CHIPS = [
    ("s1_hmz2", 1424, 314),
    ("s2_xf2",  1672, 314),
    ("s3_ds2",  1424, 531),
]
# free-area drop points (fullscreen 1080p coords)
DROPS = [(1355, 640), (1565, 540), (1460, 750)]


def main():
    for (chip, sx, sy), (tx, ty) in zip(CHIPS, DROPS):
        r = httpio.op("drag_to", from_x=sx - 8, from_y=sy - 31, to_x=tx - 8, to_y=ty - 31, duration=1.5)
        print(f"[{chip}] {r}", flush=True)
        time.sleep(0.9)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
