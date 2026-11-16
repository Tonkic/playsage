import json
import sys
import time

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8")
import httpio

# coordinates: SRA space = client minus (8,31)
LAYOUT = [
    ("L_ld",  "grid", (1432-8, 345-31), [(0,0),(0,1),(0,2),(1,1),(1,2)]),
    ("P_z1",  "grid", (1672-8, 345-31), [(5,1),(5,2),(5,3),(6,1),(6,2)]),
    ("P_z2",  "grid", (1672-8, 345-31), [(0,4),(0,5),(1,4),(1,5),(2,5)]),
    ("T_ld",  "star", (1432-8, 345-31), [(1,0),(2,0),(2,1),(3,0)]),
    ("L_zhg", "star", (1672-8, 345-31), [(0,3),(1,3),(2,2),(2,3)]),
    ("Z_xb1", "grid", (1432-8, 780-31), [(2,4),(3,4),(3,5),(4,5)]),
    ("Z_xb2", "star", (1672-8, 562-31), [(5,4),(5,5),(6,3),(6,4)]),
    ("S_xb",  "star", (1672-8, 780-31), [(3,1),(4,0),(4,1),(5,0)]),
    ("S_ld2", "grid", (1672-8, 562-31), [(3,2),(3,3),(4,3),(4,4)]),
]
TAB_GRID = (1410-8, 180-31)
TAB_STAR = (1552-8, 180-31)
GX0, GY0, GW, GH = 670.5-8, 273.0-31, 79.3, 84.5


def centroid(cells):
    return (sum(p[0] for p in cells) / len(cells), sum(p[1] for p in cells) / len(cells))


def main():
    # reset
    httpio.op("click_point", mode="abs", x=1248-8, y=985-31, after_sleep=1.5)
    httpio.op("click_point", mode="abs", x=1182-8, y=672-31, after_sleep=2.5)
    print("reset", flush=True)

    current_tab = None
    for chip, tab, slot, cells in LAYOUT:
        if tab != current_tab:
            txy = TAB_GRID if tab == "grid" else TAB_STAR
            httpio.op("click_point", mode="abs", x=txy[0], y=txy[1], after_sleep=0.9)
            current_tab = tab
        tc = centroid(cells)
        tpx = int(GX0 + GW * (tc[0] + 0.5))
        tpy = int(GY0 + GH * (tc[1] + 0.5))
        httpio.op("drag_to", from_x=slot[0], from_y=slot[1], to_x=tpx, to_y=tpy, duration=1.5)
        time.sleep(0.9)
        print(f"[{chip}] placed", flush=True)

    time.sleep(2)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
