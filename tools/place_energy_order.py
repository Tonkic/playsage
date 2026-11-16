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


# placements: slot SRA coords -> drop cell-center SRA coords (client - 8,-31)
# broken cells: (4,2),(4,3),(4,4) — avoid column 4 rows 2-4
placements = [
    ("s1_hmz", 1424, 314, 702, 284),   # 毁灭者 Z -> (0,0)-(2,1), drop (0,0)
    ("s2_xf",  1672, 314, 940, 284),   # 先锋 O -> (3,0)-(4,1), drop (3,0)
    ("s3_ds",  1424, 531, 1099, 284),  # 斗士 L -> (5,0)-(6,2), drop (5,0)
    ("s6_dm",  1672, 749, 702, 453),   # 毁灭者 dm -> (0,2),(0,3), drop (0,2)
    ("s5_dm",  1424, 749, 861, 538),   # 先锋 dm -> (2,3),(3,3), drop (2,3)
]
for chip, sx, sy, tx, ty in placements:
    ok = api("drag_to", from_x=sx, from_y=sy, to_x=tx, to_y=ty, duration=1.5)
    log(f"[{chip}] {ok}")
    time.sleep(0.7)

# scroll chip list down to find second 斗士
log("scrolling for second 斗士...")
api("scroll", clicks=-5, x=1432, y=600)
time.sleep(1.2)
# new slots after scroll: try placing from visible slot area again
# second 斗士: try slot area (1424, 531) and (1424, 640)
api("drag_to", from_x=1424, from_y=531, to_x=1150, to_y=284, duration=1.5)
time.sleep(0.8)
log("second 斗士 attempt done")

# deselect and submit
api("click_point", mode="abs", x=1142, y=580, after_sleep=0.8)
api("click_point", mode="abs", x=948, y=942, after_sleep=2.5)
api("click_point", mode="abs", x=1166, y=683, after_sleep=2)
log("SUBMIT clicked - verify revenue")
