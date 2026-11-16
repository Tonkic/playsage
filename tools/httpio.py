import json
from urllib.request import Request, urlopen

def op(method, **params):
    req = Request("http://127.0.0.1:5000/api/operator/call",
                  data=json.dumps({"method": method, "params": params}).encode(),
                  method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode()).get("success", False)
    except Exception as e:
        print("op error:", e, flush=True)
        return False
