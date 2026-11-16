import asyncio
import sys
import time

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8")
from puzzle_driver import SRA, ghost_cells

WL, WT = 8, 31
GX0, GY0, GW, GH = 670.5, 273.0, 79.3, 84.5

TARGET = [(0, 0), (0, 1), (0, 2), (1, 1), (1, 2)]
tx = sum(p[0] for p in TARGET) / 5
ty = sum(p[1] for p in TARGET) / 5
tpx = WL + GX0 + GW * (tx + 0.5)
tpy = WL + 0 + GY0 + GH * (ty + 0.5) if False else WT + GY0 + GH * (ty + 0.5)


async def main():
    async with SRA() as sra:
        await sra.revive()
        await sra.op("set_window_context")
        await asyncio.sleep(0.4)

        # down at slot1
        print("down:", await sra.op("mouse_down", x=1432, y=345))
        await asyncio.sleep(0.4)

        # closed-loop movement to the target
        for step in range(40):
            pos = await sra.op("get_mouse_pos") if False else None
            r = await sra.sess.call_tool("sra_operator_call",
                                         {"method": "get_cursor_pos", "parameters": None})
            txt = ""
            for b in r.content:
                if b.type == "text":
                    txt = b.text
            try:
                d = json.loads(txt)
                cx, cy = d.get("data", (0, 0))
            except Exception:
                print("no pos op:", txt[:80]); return
            dx = tpx - cx
            dy = tpy - cy
            if abs(dx) < 3 and abs(dy) < 3:
                print(f"reached at step {step}: ({cx},{cy})")
                break
            mx = max(-60, min(60, int(dx)))
            my = max(-60, min(60, int(dy)))
            await sra.op("move_rel", x_offset=mx, y_offset=my)
            await asyncio.sleep(0.06)
        else:
            print("did not reach target in 40 steps")

        await asyncio.sleep(0.5)
        print("up:", await sra.op("mouse_up"))
        await asyncio.sleep(1.2)
        img = await sra.shot()
        img.save(r"runs\observations\sra\closedloop_test.png")
        print("ghost p:", sorted(ghost_cells(img, "p")))

import json
asyncio.run(main())
