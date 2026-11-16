import json
import sys
import time

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8")
import httpio

# the solver layout with per-chip rotation fix attempts
LAYOUT = [
    ("L_ld",  "grid", (1432, 345), [(0,0),(0,1),(0,2),(1,1),(1,2)]),
    ("P_z1",  "grid", (1672, 345), [(5,1),(5,2),(5,3),(6,1),(6,2)]),
    ("P_z2",  "grid", (1672, 345), [(0,4),(0,5),(1,4),(1,5),(2,5)]),
    ("T_ld",  "star", (1432, 345), [(1,0),(2,0),(2,1),(3,0)]),
    ("L_zhg", "star", (1672, 345), [(0,3),(1,3),(2,2),(2,3)]),
    ("Z_xb1", "grid", (1432, 780), [(2,4),(3,4),(3,5),(4,5)]),
    ("Z_xb2", "star", (1672, 562), [(5,4),(5,5),(6,3),(6,4)]),
    ("S_xb",  "star", (1672, 780), [(3,1),(4,0),(4,1),(5,0)]),
    ("S_ld2", "grid", (1672, 562), [(3,2),(3,3),(4,3),(4,4)]),
]
TAB_GRID = (1410, 180)
TAB_STAR = (1552, 180)
GX0, GY0, GW, GH = 670.5, 273.0, 79.3, 84.5
OX, OY = 8, 31


def centroid(cells):
    return (sum(p[0] for p in cells) / len(cells), sum(p[1] for p in cells) / len(cells))


def main():
    # reset
    httpio.op("click_point", mode="abs", x=1248 + OX, y=985 + OY, after_sleep=1.5)
    httpio.op("click_point", mode="abs", x=1182 + OX, y=672 + OY, after_sleep=2.5)
    print("reset", flush=True)

    current_tab = None
    for chip, tab, slot, cells in LAYOUT:
        if tab != current_tab:
            txy = TAB_GRID if tab == "grid" else TAB_STAR
            httpio.op("click_point", mode="abs", x=txy[0] , y=txy[1], after_sleep=0.9)
            current_tab = tab
        tc = centroid(cells)
        tpx = OX + GX0 + GW * (tc[0] + 0.5)
        tpy = OY + GY0 + GH * (tc[1] + 0.5)
        sx, sy = slot[0] + OX, slot[1] + OY
        httpio.op("drag_to", from_x=sx, from_y=sy, to_x=int(tpx), to_y=int(tpy), duration=1.5)
        time.sleep(0.9)
        print(f"[{chip}] placed (verify visually later)", flush=True)

    time.sleep(2)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
