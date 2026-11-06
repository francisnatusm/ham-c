"""Run the three README demos against a live HAM-C server."""
from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:5000"


def api(method: str, path: str, data=None):
    req = urllib.request.Request(BASE + path, method=method)
    if data is not None:
        body = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
        req.data = body
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode()), r.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            payload = json.loads(body)
        except Exception:
            payload = {"error": body}
        return payload, exc.code


def send(chat_id: int, text: str):
    data, status = api("POST", f"/api/chats/{chat_id}/messages", {"text": text})
    print(f"> {text}")
    if status >= 400:
        print(f"! ERROR {status}: {data.get('error', data)}")
        return data
    print(f"< {data['message']['content']}")
    if data.get("saved_facts"):
        print("  saved:", data["saved_facts"])
    if data.get("used_facts"):
        print("  used:", data["used_facts"])
    return data


def new_chat():
    data, _ = api("POST", "/api/chats")
    return data["id"]


def main():
    state, _ = api("GET", "/api/state")
    print("chatgpt_ready:", state.get("chatgpt_ready"))
    print()

    print("=== TEST 1: codeword recall ===")
    cid = new_chat()
    for t in [
        "Hello, this is filler about weather.",
        "The project codeword is ORANGE-17.",
        "More filler about lunch plans.",
        "What is the project codeword?",
    ]:
        send(cid, t)
    print()

    print("=== TEST 2: campus update ===")
    cid = new_chat()
    send(cid, "I study at Campus North.")
    send(cid, "Which campus am I on?")
    cid = new_chat()
    send(cid, "I transferred to Campus South.")
    send(cid, "Which campus am I on?")
    print()

    print("=== TEST 3: delete removes research_id ===")
    cid_save = new_chat()
    send(cid_save, "Remember the temporary research ID is BLUE-88.")
    cid_ask = new_chat()
    send(cid_ask, "What is my research ID?")
    deleted, _ = api("POST", f"/api/chats/{cid_save}/delete")
    print("deleted:", deleted.get("removed_facts"))
    send(cid_ask, "What is my research ID?")
    state, _ = api("GET", "/api/state")
    print("active facts:", [(f["key"], f["value"]) for f in state["facts"]])


if __name__ == "__main__":
    main()
