import json
import http.cookiejar
import urllib.request

BASE = "http://127.0.0.1:5000"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, data=None):
    req = urllib.request.Request(BASE + path, method=method)
    if data is not None:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with opener.open(req) as r:
        return json.loads(r.read().decode())


me = call("GET", "/api/auth/me")
print("start", me)
assert me["auth_required"] is True

guest = call("POST", "/api/auth/guest")
print("guest", guest["mode"])
state = call("GET", "/api/state")
print("guest chats", len(state["chats"]), "facts", len(state["facts"]))
chat = call("POST", "/api/chats")
call("POST", f"/api/chats/{chat['id']}/messages", {"text": "The project codeword is ORANGE-17."})
state = call("GET", "/api/state")
print("after save facts", [(f["key"], f["value"]) for f in state["facts"]])

# new guest should not see previous
jar.clear()
call("POST", "/api/auth/guest")
state2 = call("GET", "/api/state")
print("new guest facts", [(f["key"], f["value"]) for f in state2["facts"]])
assert not any(f["value"] == "ORANGE-17" for f in state2["facts"])

# register + login persistence
email = "demo.hamc@example.com"
try:
    user = call(
        "POST",
        "/api/auth/register",
        {
            "email": email,
            "password": "secret12",
            "display_name": "Demo User",
            "nickname": "Demo",
        },
    )
except Exception:
    user = call("POST", "/api/auth/login", {"email": email, "password": "secret12"})
print("user", user["mode"], user["user"]["email"])
chat = call("POST", "/api/chats")
call("POST", f"/api/chats/{chat['id']}/messages", {"text": "hi i am DemoUser"})
state = call("GET", "/api/state")
print("user facts", [(f["key"], f["value"]) for f in state["facts"]])
print("ok")
