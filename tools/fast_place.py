import asyncio
import json
import sys
import time

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8")
from puzzle_driver import SRA, ghost_cells

# 9 chips, solver layout
LAYOUT = [
    ("L_ld",  "grid", (1432, 345), [(0,0),(0,1),(0,2),(1,1),(1,2)]),
    ("P_z1",  "grid", (1672, 345), [(5,1),(5,2),(5,3),(6,1),(6,2)]),
    ("P_z2",  "grid", (1672, 345), [(0,4),(0,5),(1,4),(1,5),(2,5)]),
    ("Z_xb1", "grid", (1432, 780), [(2,4),(3,4),(3,5),(4,5)]),
    ("S_ld2", "grid", (1672, 562), [(3,2),(3,3),(4,3),(4,4)]),
    ("T_ld",  "star", (1432, 345), [(1,0),(2,0),(2,1),(3,0)]),
    ("L_zhg", "star", (1672, 345), [(0,3),(1,3),(2,2),(2,3)]),
    ("Z_xb2", "star", (1672, 562), [(5,4),(5,5),(6,3),(6,4)]),
    ("S_xb",  "star", (1672, 780), [(3,1),(4,0),(4,1),(5,0)]),
]
TAB_GRID = (1410, 180)
TAB_STAR = (1552, 180)
GX0, GY0, GW, GH = 670.5, 273.0, 79.3, 84.5
WL, WT = 8, 31


def centroid(cells):
    return (sum(p[0] for p in cells) / len(cells), sum(p[1] for p in cells) / len(cells))


async def main():
    async with SRA() as sra:
        t0 = time.time()
        # FAST navigation: exit current (if puzzle) -> workshop -> orders -> start -> confirm
        await sra.op("click_point", mode="abs", x=60, y=63, after_sleep=2.0)
        await sra.op("press_key", key="f", wait=3.0)
        await sra.op("click_point", mode="abs", x=1523, y=848, after_sleep=2.5)
        await sra.op("click_point", mode="abs", x=1586, y=996, after_sleep=2.5)
        await sra.op("click_point", mode="abs", x=956, y=887, after_sleep=2.5)
        print(f"nav done at {time.time()-t0:.0f}s", flush=True)

        current_tab = None
        for chip, tab, slot, cells in LAYOUT:
            if time.time() - t0 > 150:
                print(f"TIME BUDGET exceeded before {chip}", flush=True)
                break
            if tab != current_tab:
                txy = TAB_GRID if tab == "grid" else TAB_STAR
                await sra.op("click_point", mode="abs", x=txy[0], y=txy[1], after_sleep=0.8)
                current_tab = tab
            tc = centroid(cells)
            tpx = WL + GX0 + GW * (tc[0] + 0.5)
            tpy = WT + GY0 + GH * (tc[1] + 0.5)
            r = await sra.op("drag_to", from_x=slot[0], from_y=slot[1],
                             to_x=int(tpx), to_y=int(tpy), duration=1.2)
            await asyncio.sleep(0.7)
            print(f"[{chip}] drag={r} at {time.time()-t0:.0f}s", flush=True)

        await asyncio.sleep(1.5)
        img = await sra.shot()
        img.save(r"runs\observations\sra\fast_all_done.png")
        print("ghost p:", sorted(ghost_cells(img, "p")), flush=True)
        print("TOTAL:", f"{time.time()-t0:.0f}s", flush=True)

asyncio.run(main())
