import json
import sys
import time

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8")
import httpio

# s5 先锋 domino -> cells (0,2),(1,2): centroid client (750,484) -> SRA (742,453)
r = httpio.op("drag_to", from_x=1424 - 8, from_y=749 - 31, to_x=742, to_y=453, duration=1.2)
print("s5:", r, flush=True)
time.sleep(0.9)

# s6 毁灭者 domino -> cells (2,2),(2,3): centroid client (869,569) -> SRA (861,538)
r = httpio.op("drag_to", from_x=1672 - 8, from_y=749 - 31, to_x=861, to_y=538, duration=1.2)
print("s6:", r, flush=True)
time.sleep(0.9)
print("DONE", flush=True)
