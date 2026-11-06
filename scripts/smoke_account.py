import json
import uuid
import http.cookiejar
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:5000"


def client():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(method, path, data=None):
        req = urllib.request.Request(BASE + path, method=method)
        if data is not None:
            req.data = json.dumps(data).encode()
            req.add_header("Content-Type", "application/json")
        try:
            with opener.open(req) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                return e.code, json.loads(body)
            except Exception:
                return e.code, {"error": body}

    return call


call = client()
email_a = f"alice_{uuid.uuid4().hex[:8]}@example.com"
code, me = call(
    "POST",
    "/api/auth/register",
    {
        "email": email_a,
        "password": "secret12",
        "display_name": "Alice Demo",
        "nickname": "Ali",
    },
)
assert code == 200, me
assert me["user"]["initial"] == "A"
assert me["user"]["display_name"] == "Alice Demo"
assert me["user"]["nickname"] == "Ali"
chat = call("POST", "/api/chats")[1]
call(
    "POST",
    f"/api/chats/{chat['id']}/messages",
    {"text": "The project codeword is ORANGE-17."},
)
facts_a = call("GET", "/api/state")[1]["facts"]
assert any(f["value"] == "ORANGE-17" for f in facts_a), facts_a

code, out = call(
    "POST",
    "/api/account/profile",
    {"display_name": "Alice D", "nickname": "Ally"},
)
assert code == 200 and out["user"]["display_name"] == "Alice D", out
assert out["user"]["nickname"] == "Ally"
code, out = call(
    "POST",
    "/api/account/password",
    {"current_password": "secret12", "new_password": "secret99"},
)
assert code == 200, out

call("POST", "/api/auth/logout")
call("POST", "/api/auth/guest")
facts_g = call("GET", "/api/state")[1]["facts"]
assert not any(f.get("value") == "ORANGE-17" for f in facts_g), facts_g

code, me = call("POST", "/api/auth/login", {"email": email_a, "password": "secret99"})
assert code == 200 and me["user"]["display_name"] == "Alice D", me
assert me["user"]["nickname"] == "Ally"
facts_back = call("GET", "/api/state")[1]["facts"]
assert any(f["value"] == "ORANGE-17" for f in facts_back), facts_back

call_b = client()
email_b = f"bob_{uuid.uuid4().hex[:8]}@example.com"
code, meb = call_b(
    "POST",
    "/api/auth/register",
    {
        "email": email_b,
        "password": "bobpass1",
        "display_name": "Bob Builder",
        "nickname": "Bob",
    },
)
assert code == 200, meb
facts_b = call_b("GET", "/api/state")[1]["facts"]
assert not any(f.get("value") == "ORANGE-17" for f in facts_b), facts_b
chat_b = call_b("POST", "/api/chats")[1]
call_b(
    "POST",
    f"/api/chats/{chat_b['id']}/messages",
    {"text": "Remember the temporary research ID is BLUE-88."},
)
facts_b2 = call_b("GET", "/api/state")[1]["facts"]
assert any("BLUE-88" in f["value"] for f in facts_b2), facts_b2

facts_a2 = call("GET", "/api/state")[1]["facts"]
assert any(f["value"] == "ORANGE-17" for f in facts_a2)
assert not any("BLUE-88" in f.get("value", "") for f in facts_a2)

code, out = call_b("POST", "/api/account/delete", {"password": "bobpass1"})
assert code == 200, out
code, me = call_b("POST", "/api/auth/login", {"email": email_b, "password": "bobpass1"})
assert code == 401, me

print("ALL OK")
print("alice", email_a)
print("bob deleted", email_b)
