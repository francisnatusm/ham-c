"""HAM-C web app: the user talks here, not on the ChatGPT website."""

from __future__ import annotations

import os
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from hamc.chatgpt import ChatGPTClient
from hamc.mailer import send_account_deleted_email, send_welcome_email
from hamc.orchestrator import Orchestrator
from hamc.store import EMAIL_RE, Store

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

app = Flask(__name__)
app.secret_key = os.getenv("HAMC_SECRET", secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=30)

def database_path() -> Path:
    # Vercel only allows writes in /tmp, and that file is wiped between cold starts.
    if os.getenv("VERCEL"):
        return Path("/tmp/hamc.db")
    return ROOT / "data" / "hamc.db"


store = Store(database_path())
client = ChatGPTClient()
hamc = Orchestrator(store, client)


def owner() -> tuple[int | None, str | None]:
    """Return (user_id, guest_id) for the current session."""
    user_id = session.get("user_id")
    if user_id is not None:
        return int(user_id), None
    guest_id = session.get("guest_id")
    if guest_id:
        return None, str(guest_id)
    return None, None


def require_owner():
    user_id, guest_id = owner()
    if user_id is None and not guest_id:
        return None, None, (jsonify({"error": "Sign in or continue as guest first.", "auth_required": True}), 401)
    return user_id, guest_id, None


def user_payload(user: dict) -> dict:
    name = (user.get("display_name") or user["email"].split("@")[0] or "U").strip()
    nick = (user.get("nickname") or name.split()[0] or "User").strip()
    initial = name[0].upper() if name else "U"
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": name,
        "nickname": nick,
        "initial": initial,
        "created_at": user.get("created_at"),
    }


@app.get("/")
def home():
    return render_template(
        "index.html",
        chatgpt_ready=client.available,
        model=client.model if client.available else "local fallback",
    )


@app.get("/manifest.webmanifest")
def web_manifest():
    response = send_from_directory(ROOT / "static", "manifest.webmanifest")
    response.headers["Content-Type"] = "application/manifest+json"
    return response


@app.get("/sw.js")
def service_worker():
    response = send_from_directory(ROOT / "static", "sw.js")
    response.headers["Content-Type"] = "application/javascript"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.get("/api/auth/me")
def auth_me():
    user_id, guest_id = owner()
    if user_id is not None:
        user = store.get_user(user_id)
        if not user:
            session.clear()
            return jsonify({"mode": "none", "auth_required": True})
        return jsonify(
            {
                "mode": "user",
                "auth_required": False,
                "user": user_payload(user),
                "chatgpt_ready": client.available,
            }
        )
    if guest_id:
        return jsonify(
            {
                "mode": "guest",
                "auth_required": False,
                "guest_id": guest_id,
                "chatgpt_ready": client.available,
            }
        )
    return jsonify({"mode": "none", "auth_required": True, "chatgpt_ready": client.available})


@app.post("/api/auth/guest")
def auth_guest():
    session.clear()
    session["guest_id"] = str(uuid.uuid4())
    session.permanent = False
    return jsonify({"mode": "guest", "guest_id": session["guest_id"]})


@app.post("/api/auth/register")
def auth_register():
    data = request.get_json(force=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    display_name = str(data.get("display_name", "")).strip()
    nickname = str(data.get("nickname", "")).strip()
    if not display_name:
        return jsonify({"error": "Enter your name."}), 400
    if not nickname:
        return jsonify({"error": "Enter a nickname."}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    if store.get_user_by_email(email):
        return jsonify({"error": "That email is already registered. Sign in instead."}), 409
    user = store.create_user(
        email,
        generate_password_hash(password),
        display_name=display_name,
        nickname=nickname,
    )
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    send_welcome_email(user["email"], user.get("display_name") or display_name, user.get("nickname") or nickname)
    return jsonify({"mode": "user", "user": user_payload(user)})


@app.post("/api/auth/login")
def auth_login():
    data = request.get_json(force=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    row = store.get_user_by_email(email)
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Wrong email or password."}), 401
    session.clear()
    session["user_id"] = row["id"]
    session.permanent = True
    user = store.get_user(row["id"])
    return jsonify({"mode": "user", "user": user_payload(user)})


@app.post("/api/auth/logout")
def auth_logout():
    session.clear()
    return jsonify({"ok": True, "mode": "none", "auth_required": True})


@app.post("/api/account/profile")
def account_profile():
    user_id, _, err = require_owner()
    if err:
        return err
    if user_id is None:
        return jsonify({"error": "Sign in required."}), 401
    data = request.get_json(force=True) or {}
    name = str(data.get("display_name", "")).strip()
    nickname = str(data.get("nickname", "")).strip()
    if len(name) < 1:
        return jsonify({"error": "Name cannot be empty."}), 400
    if len(nickname) < 1:
        return jsonify({"error": "Nickname cannot be empty."}), 400
    user = store.update_user_profile(user_id, name, nickname=nickname)
    return jsonify({"user": user_payload(user)})


@app.post("/api/account/password")
def account_password():
    user_id, _, err = require_owner()
    if err:
        return err
    if user_id is None:
        return jsonify({"error": "Sign in required."}), 401
    data = request.get_json(force=True) or {}
    current = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))
    if len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400
    row = store.get_user_by_email(store.get_user(user_id)["email"])
    if not row or not check_password_hash(row["password_hash"], current):
        return jsonify({"error": "Current password is wrong."}), 401
    store.update_user_password(user_id, generate_password_hash(new_password))
    return jsonify({"ok": True})


@app.post("/api/account/delete")
def account_delete():
    user_id, _, err = require_owner()
    if err:
        return err
    if user_id is None:
        return jsonify({"error": "Sign in required."}), 401
    data = request.get_json(force=True) or {}
    password = str(data.get("password", ""))
    user = store.get_user(user_id)
    row = store.get_user_by_email(user["email"]) if user else None
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Password is wrong."}), 401
    email = user["email"]
    display_name = user.get("display_name") or ""
    nickname = user.get("nickname") or ""
    store.delete_user(user_id)
    session.clear()
    send_account_deleted_email(email, display_name, nickname)
    return jsonify({"ok": True, "mode": "none"})


@app.get("/api/state")
def state():
    user_id, guest_id, err = require_owner()
    if err:
        return err
    chats = store.list_chats(user_id=user_id, guest_id=guest_id)
    # Only open a chat when the client asks for one (fresh login = welcome / new chat).
    chat_id = request.args.get("chat_id", type=int)
    chat = store.get_chat(chat_id, user_id=user_id, guest_id=guest_id) if chat_id else None
    messages = store.list_messages(chat["id"]) if chat else []
    return jsonify(
        {
            "chats": chats,
            "chat": chat,
            "messages": messages,
            "facts": store.active_facts(user_id=user_id, guest_id=guest_id),
            "chatgpt_ready": client.available,
            "mode": "user" if user_id else "guest",
        }
    )


@app.post("/api/chats")
def new_chat():
    user_id, guest_id, err = require_owner()
    if err:
        return err
    chat = store.create_chat(user_id=user_id, guest_id=guest_id)
    return jsonify(chat)


@app.post("/api/chats/<int:chat_id>/messages")
def send_message(chat_id: int):
    user_id, guest_id, err = require_owner()
    if err:
        return err
    if not store.owns_chat(chat_id, user_id, guest_id):
        return jsonify({"error": "Chat not found"}), 404
    data = request.get_json(force=True) or {}
    text = str(data.get("text", "")).strip()
    if not text:
        return jsonify({"error": "Empty message"}), 400
    try:
        result = hamc.send(chat_id, text, user_id=user_id, guest_id=guest_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:
        return jsonify({"error": f"HAM-C failed: {exc}"}), 500
    return jsonify(result)


@app.post("/api/chats/<int:chat_id>/delete")
def delete_chat(chat_id: int):
    user_id, guest_id, err = require_owner()
    if err:
        return err
    if not store.owns_chat(chat_id, user_id, guest_id):
        return jsonify({"error": "Chat not found"}), 404
    removed = store.delete_chat(chat_id)
    return jsonify(
        {
            "ok": True,
            "removed_facts": [
                {"id": f["id"], "key": f["key"], "value": f["value"]} for f in removed
            ],
        }
    )


@app.post("/api/facts/<int:fact_id>/delete")
def delete_fact(fact_id: int):
    user_id, guest_id, err = require_owner()
    if err:
        return err
    if not store.owns_fact(fact_id, user_id, guest_id):
        return jsonify({"error": "Fact not found"}), 404
    fact = store.delete_fact(fact_id)
    if not fact:
        return jsonify({"error": "Fact not found"}), 404
    return jsonify(fact)


if __name__ == "__main__":
    port = int(os.getenv("HAMC_PORT", "5000"))
    # 0.0.0.0 = reachable from phone/other devices on the same Wi-Fi
    host = os.getenv("HAMC_HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=True)
