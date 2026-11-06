"""Guest data must not survive a new page-load guest session; login must persist."""
import json
import http.cookiejar
import urllib.request

BASE = "http://127.0.0.1:5000"


def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def call(opener, method, path, data=None):
    req = urllib.request.Request(BASE + path, method=method)
    if data is not None:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with opener.open(req) as r:
        return json.loads(r.read().decode())


op, _ = client()
call(op, "POST", "/api/auth/guest")
chat = call(op, "POST", "/api/chats")
call(op, "POST", f"/api/chats/{chat['id']}/messages", {"text": "The project codeword is ORANGE-17."})
facts = call(op, "GET", "/api/state")["facts"]
assert any(f["value"] == "ORANGE-17" for f in facts), facts
print("guest saved ORANGE-17")

# Simulate refresh: app always mints a new guest session
call(op, "POST", "/api/auth/guest")
facts2 = call(op, "GET", "/api/state")["facts"]
assert not any(f["value"] == "ORANGE-17" for f in facts2), facts2
print("after refresh-guest: empty OK")

# Login persists across "refresh" (same cookie, no new guest)
email = "persist.hamc@example.com"
try:
    call(op, "POST", "/api/auth/register", {"email": email, "password": "secret12"})
except Exception:
    call(op, "POST", "/api/auth/login", {"email": email, "password": "secret12"})
chat = call(op, "POST", "/api/chats")
call(op, "POST", f"/api/chats/{chat['id']}/messages", {"text": "hi i am PersistUser"})
facts3 = call(op, "GET", "/api/state")["facts"]
assert any(f.get("value") == "PersistUser" for f in facts3), facts3

# Same user session still sees facts (no guest rotate)
me = call(op, "GET", "/api/auth/me")
assert me["mode"] == "user"
facts4 = call(op, "GET", "/api/state")["facts"]
assert any(f.get("value") == "PersistUser" for f in facts4), facts4
print("logged-in persists OK")
print("all good")
