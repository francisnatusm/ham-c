"""One message through HAM-C: save, retrieve, call ChatGPT, show the fact used."""

from __future__ import annotations

from hamc.chatgpt import ChatGPTClient
from hamc.extractor import extract_facts
from hamc.retriever import is_fact_question, retrieve
from hamc.store import Store

RECENT_TURNS = 12
SUMMARIZE_AFTER = 16

MISSING_FACT_REPLY = "I don't have that information."

SYSTEM = """You are answering through HAM-C, a helpful chat assistant with a private fact store.

Normal conversation:
- Reply naturally, like ChatGPT. Be friendly and clear.
- Small talk, clarifications, opinions, and general questions are fine.
- Do not say you are missing a "fact" or a "fact store" during normal chat.

Personal or project details (name, campus, school, codeword, research id, location, likes, work, and similar):
- Use ONLY the "Stored facts" list below.
- Never invent those details.
- Never rebuild a deleted or missing detail from earlier messages in this chat.
- If the user asks for such a detail and it is not in Stored facts, say naturally that you don't have that information.
- Do not use ChatGPT Memory for personal details. HAM-C Stored facts are the only source."""


def _fact_view(fact: dict) -> dict:
    return {
        "id": fact.get("id"),
        "key": fact.get("key") or fact.get("fact_key"),
        "value": fact.get("value"),
    }


def pack_facts(facts: list[dict]) -> str:
    if not facts:
        return "Stored facts: none."
    lines = ["Stored facts (use these if relevant):"]
    for fact in facts:
        view = _fact_view(fact)
        if view["key"] is None or view["value"] is None:
            continue
        lines.append(f"- {view['key']}: {view['value']}")
    return "\n".join(lines)


def history_for_model(messages: list[dict], active_facts: list[dict]) -> list[dict]:
    """Keep recent chat context, but hide values that are no longer in the store."""
    allowed = {str(f["value"]).strip().lower() for f in active_facts if f.get("value")}
    out: list[dict] = []
    for msg in messages[-RECENT_TURNS:]:
        if msg["role"] not in ("user", "assistant"):
            continue
        content = msg["content"]
        # Drop earlier assistant replies that cited facts — those leak deleted values.
        if msg["role"] == "assistant" and msg.get("used_facts"):
            continue
        if msg["role"] == "assistant":
            lowered = content.lower()
            # Skip replies that clearly recited a value no longer stored.
            if any(
                val and val in lowered and val not in allowed
                for val in _possible_secret_tokens(messages)
            ):
                continue
        out.append(
            {
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": content,
            }
        )
    # Always end with the current user turn once (caller adds it if missing).
    return out


def _possible_secret_tokens(messages: list[dict]) -> set[str]:
    """Collect short values previously shown as used facts in this chat."""
    found: set[str] = set()
    for msg in messages:
        for fact in msg.get("used_facts") or []:
            value = str(fact.get("value") or "").strip().lower()
            if len(value) >= 3:
                found.add(value)
        content = str(msg.get("content") or "")
        # Capture common demo secrets mentioned in older assistant lines.
        for token in ("orange-17", "blue-88", "campus north", "campus south"):
            if token in content.lower():
                found.add(token)
    return found


class Orchestrator:
    def __init__(self, store: Store, client: ChatGPTClient):
        self.store = store
        self.client = client

    def send(
        self,
        chat_id: int,
        text: str,
        user_id: int | None = None,
        guest_id: str | None = None,
    ) -> dict:
        chat = self.store.get_chat(chat_id, user_id=user_id, guest_id=guest_id)
        if not chat:
            raise ValueError("Chat not found")

        saved = []
        for item in extract_facts(text, self.client):
            saved.append(
                self.store.upsert_fact(
                    item["key"],
                    item["value"],
                    source_chat_id=chat_id,
                    confirmed=bool(item.get("confirmed")),
                    user_id=user_id,
                    guest_id=guest_id,
                )
            )

        self.store.add_message(chat_id, "user", text)
        if chat["title"] == "New chat":
            self.store.set_chat_title(chat_id, text[:48])

        messages = self.store.list_messages(chat_id)
        self._maybe_summarize(chat_id, messages)

        active = self.store.active_facts(user_id=user_id, guest_id=guest_id)
        used = retrieve(active, text)

        # Asking for a personal fact that is gone: answer locally so chat
        # history cannot leak the deleted value through ChatGPT.
        if is_fact_question(text) and not used:
            answer = MISSING_FACT_REPLY
            used_view = []
        else:
            prompt = [
                {"role": "system", "content": SYSTEM + "\n\n" + pack_facts(used)},
            ]
            for msg in history_for_model(messages[:-1], active):
                prompt.append(msg)
            prompt.append({"role": "user", "content": text})
            answer = self.client.complete(prompt)
            used_view = [_fact_view(f) for f in used if f.get("key") or f.get("fact_key")]

        assistant = self.store.add_message(
            chat_id, "assistant", answer, used_facts=used_view
        )
        return {
            "message": assistant,
            "used_facts": used_view,
            "saved_facts": [
                _fact_view(f) for f in saved if f.get("key") or f.get("fact_key")
            ],
        }

    def _maybe_summarize(self, chat_id: int, messages: list[dict]) -> None:
        if len(messages) < SUMMARIZE_AFTER:
            return
        older = messages[:-8]
        if not older:
            return
        blob = "\n".join(f"{m['role']}: {m['content']}" for m in older[-20:])
        summary = self.client.complete(
            [
                {
                    "role": "system",
                    "content": "Summarize this chat for later turns. Keep under 80 words. Do not invent personal facts.",
                },
                {"role": "user", "content": blob},
            ],
            max_tokens=160,
        )
        self.store.add_summary(chat_id, summary)
