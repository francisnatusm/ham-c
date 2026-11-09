"""One message through HAM-C: save, retrieve, call ChatGPT, show the fact used."""

from __future__ import annotations

from hamc.chatgpt import ChatGPTClient
from hamc.extractor import extract_facts
from hamc.retriever import retrieve
from hamc.store import Store

SUMMARIZE_AFTER = 16


SYSTEM = """You are answering through HAM-C, a memory layer in front of ChatGPT.
HAM-C is the only source of personal or project facts.
Use ONLY the "Stored facts" list below for any personal detail (name, campus, codeword, id, school, location, likes, work, and similar).
If the needed fact is missing from that list, say you do not have it.
Do not invent facts. Do not use ChatGPT Memory.
Do not reconstruct a deleted or missing fact from wording in the user's message alone when they are asking a recall question.
If Stored facts is none or does not contain the answer, reply that you do not have that fact stored."""


def pack_facts(facts: list[dict]) -> str:
    if not facts:
        return "Stored facts: none."
    lines = ["Stored facts (use these if relevant):"]
    for fact in facts:
        lines.append(f"- {fact['key']}: {fact['value']}")
    return "\n".join(lines)


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

        used = retrieve(self.store.active_facts(user_id=user_id, guest_id=guest_id), text)
        # Do not send prior chat turns or summaries to the model. Those still
        # contain deleted facts and would let ChatGPT answer without HAM-C.
        prompt = [
            {"role": "system", "content": SYSTEM + "\n\n" + pack_facts(used)},
            {"role": "user", "content": text},
        ]

        answer = self.client.complete(prompt)
        used_view = [
            {"id": f["id"], "key": f["key"], "value": f["value"]} for f in used
        ]
        assistant = self.store.add_message(
            chat_id, "assistant", answer, used_facts=used_view
        )
        return {
            "message": assistant,
            "used_facts": used_view,
            "saved_facts": [
                {"id": f["id"], "key": f["key"], "value": f["value"]} for f in saved
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
                    "content": "Summarize this chat so later turns keep the important facts. Keep it under 80 words.",
                },
                {"role": "user", "content": blob},
            ],
            max_tokens=160,
        )
        self.store.add_summary(chat_id, summary)
