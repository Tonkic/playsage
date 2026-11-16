import json
import sys
import time
from urllib.request import Request, urlopen

sys.stdout.reconfigure(encoding="utf-8")


def api(method, **params):
    req = Request("http://127.0.0.1:5000/api/operator/call",
                  data=json.dumps({"method": method, "params": params}).encode(),
                  method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()).get("success", False)
    except Exception as e:
        print("err:", e, flush=True)
        return False


t0 = time.time()
def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)


# 1. restart game
api("kill")
time.sleep(5)
api("launch", channel=0, path=r"D:\Star Rail\Game\StarRail.exe")
log("game launched")
time.sleep(75)

# 2. welcome -> world
api("set_window_context")
api("active_window")
time.sleep(1)
api("click_point", mode="rel", x=0.5, y=0.5, after_sleep=3)
log("world entered")
time.sleep(25)

# 3. workshop -> orders -> puzzle
api("press_key", key="f", wait=3.5)
time.sleep(1)
api("click_point", mode="abs", x=1523, y=848, after_sleep=2.5)
api("click_point", mode="abs", x=1586, y=996, after_sleep=2.5)
api("click_point", mode="abs", x=956, y=887, after_sleep=2.5)
log("puzzle opened")

# 4. place ALL 12 chips (6 types × 2 copies each)
# grid layout: 7x6, broken cells at (4,2),(4,5); fills 40 cells exactly
# grid tab (slots 1-6 first copies): (1432,345),(1680,345),(1432,562),(1680,562),(1432,780),(1680,780)
# star tab (slots 1-6 second copies): same coords
# each slot: drag to a drop point; the drop = the cell center for in-cell placement

# tab 1 (grid): 6 chips
grid_placements = [
    # slot1 毁灭者(Z-shape 4c) -> (0,0)-(2,1), drop (0,0) center
    (1424, 314, 702, 284),
    # slot2 指挥官(P-shape 4c) -> (3,0)-(4,1), drop (3,0) center
    (1672, 314, 940, 284),
    # slot3 斗士(L 4c) -> (5,0)-(6,2), drop (5,0) center
    (1424, 531, 1099, 284),
    # slot5 先锋(dm 2c vert) -> (0,2),(0,3), drop (0,2) center
    (1424, 749, 702, 453),
    # slot6 毁灭者(dm 2c vert) -> (2,2),(2,3), drop (2,2) center
    (1672, 749, 861, 453),
    # slot4 信标/bar(4c) -> (3,3)-(6,4), drop (4,3) center
    (1672, 531, 1036, 609),
]
log("placing grid tab chips")
for i, (sx, sy, tx, ty) in enumerate(grid_placements):
    api("drag_to", from_x=sx, from_y=sy, to_x=tx, to_y=ty, duration=1.5)
    time.sleep(0.6)
    log(f"  grid chip {i+1} placed")

# switch to star tab for second copies
api("click_point", mode="abs", x=1544, y=149, after_sleep=1.0)
log("switched to star tab")

# tab 2 (star): 6 chips (second copies of same types)
star_placements = [
    # slot1 毁灭者(Z 4c) -> (0,3)-(1,4)+(2,4), drop (0,3) center
    (1424, 314, 702, 538),
    # slot2 指挥官(P 4c) -> (3,4)-(4,5)+(5,4), drop (3,4) center
    (1672, 314, 940, 640),
    # slot3 毁灭者(dm 2c) -> (5,4),(5,5), drop (5,4) center
    (1424, 531, 1124, 642),
    # slot4 先锋(dm 2c vert) -> (6,4),(6,5) skip if no space, drop (6,4) center
    (1672, 531, 1204, 640),
    # slot5 先锋(dm 2c) -> skip if full, drop (6,5) area
    (1424, 749, 1245, 640),
    # slot6 毁灭者(dm 2c) -> skip
    (1672, 749, 1245, 564),
]
log("placing star tab chips")
for i, (sx, sy, tx, ty) in enumerate(star_placements):
    api("drag_to", from_x=sx, from_y=sy, to_x=tx, to_y=ty, duration=1.5)
    time.sleep(0.6)
    log(f"  star chip {i+1} placed")

log("ALL 12 CHIPS PLACED - now submit")

# 5. deselect + submit
api("click_point", mode="abs", x=1142, y=580, after_sleep=0.8)
api("click_point", mode="abs", x=948, y=942, after_sleep=2.5)
api("click_point", mode="abs", x=1166, y=683, after_sleep=2)
log("SUBMITTED - check revenue")
