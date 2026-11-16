import json
import sys
import time
import subprocess
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


# 1. restart the game
api("kill")
time.sleep(5)
api("launch", channel=0, path=r"D:\Star Rail\Game\StarRail.exe")
log("game launched, waiting for boot")
time.sleep(75)

# 2. focus + welcome
api("set_window_context")
api("active_window")
time.sleep(1)
api("click_point", mode="rel", x=0.5, y=0.5, after_sleep=3)
log("world entered")
time.sleep(30)

# 3. F -> workshop -> orders -> start -> confirm
api("press_key", key="f", wait=3.5)
time.sleep(1)
api("click_point", mode="abs", x=1523, y=848, after_sleep=2.5)
api("click_point", mode="abs", x=1586, y=996, after_sleep=2.5)
api("click_point", mode="abs", x=956, y=887, after_sleep=2.5)
log("puzzle opened")

# 4. five placements (drops at in-cell centers)
placements = [
    ("s1_hmz", 1432, 345, 710, 315),    # 毁灭者 Z -> (0,0)-(2,1), drop (0,0) center
    ("s2_xf",  1680, 345, 948, 315),    # 先锋 O -> (3,0)-(4,1), drop (3,0) center
    ("s3_ds",  1432, 562, 1107, 315),   # 斗士 L -> (5,0)-(6,2), drop (5,0) center
    ("s5_xf",  1432, 780, 710, 484),    # 先锋 domino -> (0,2)-(1,2), drop (0,2) center
    ("s6_hmz", 1680, 780, 869, 484),    # 毁灭者 domino -> (2,2)-(2,3), drop (2,2) center
]
for chip, sx, sy, tx, ty in placements:
    api("drag_to", from_x=sx, from_y=sy, to_x=tx, to_y=ty, duration=1.5)
    time.sleep(0.8)
    log(f"[{chip}] placed")

log("ALL DONE")
