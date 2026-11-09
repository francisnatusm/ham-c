"""Talk to ChatGPT through the API. HAM-C owns memory; ChatGPT only writes."""

from __future__ import annotations

import os
import re


class ChatGPTClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._client = None
        if self.api_key:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete(self, messages: list[dict], max_tokens: int = 500) -> str:
        if not self._client:
            return mock_complete(messages)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
                timeout=20.0,
            )
        except Exception as exc:
            # Billing / network / auth: keep the demo usable on local fallback
            err = str(exc).lower()
            if any(
                s in err
                for s in (
                    "insufficient_quota",
                    "billing",
                    "credit",
                    "quota",
                    "429",
                    "401",
                    "403",
                    "timeout",
                    "timed out",
                    "connection",
                )
            ):
                return mock_complete(messages)
            raise RuntimeError(f"ChatGPT API error: {exc}") from exc
        return (response.choices[0].message.content or "").strip()


def mock_complete(messages: list[dict]) -> str:
    """Local fallback so the store and delete rules can be demoed without a key."""
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    facts_block = ""
    for m in messages:
        if m["role"] == "system" and "Stored facts" in m["content"]:
            facts_block = m["content"]
            break
    q = user.lower()
    facts = {}
    for line in facts_block.splitlines():
        if ":" in line and not line.startswith("Stored") and not line.startswith("Use"):
            key, value = line.split(":", 1)
            facts[key.strip().lstrip("- ").lower()] = value.strip()
    if facts.get("name") and re.search(r"\b(i am|i'm|my name is)\b", q):
        return f"Saved. Your name is stored as {facts['name']}."
    if facts.get("school") and re.search(r"\b(study|school|university)\b", q):
        if "which" in q or "where" in q or "what" in q:
            return facts["school"]
        return f"Saved. School is now {facts['school']}."
    if facts.get("like") and re.search(r"\b(like|love|enjoy|prefer)\b", q):
        if "what" in q:
            return facts["like"]
        return f"Saved. You like {facts['like']}."
    if facts.get("location") and re.search(r"\b(live|from|location|where|moved|now)\b", q):
        if "where" in q or "what" in q or "which" in q:
            return facts["location"]
        return f"Saved. Location is now {facts['location']}."
    if facts.get("work") and re.search(r"\b(work|job|company)\b", q):
        return f"Saved. Work is now {facts['work']}."
    if facts.get("campus") and re.search(r"\b(study|campus|transferred?)\b", q):
        if "which" in q or "where" in q or "am i on" in q:
            return facts["campus"]
        return f"Saved. Campus is now {facts['campus']}."
    if facts.get("codeword") and ("codeword" in q or "code word" in q):
        if "what" in q:
            return facts["codeword"]
        return f"Saved. The project codeword is {facts['codeword']}."
    if (facts.get("research_id") or facts.get("id")) and (
        "research" in q or "remember" in q or "id" in q
    ):
        rid = facts.get("research_id") or facts.get("id")
        if "what" in q:
            return rid
        return f"Saved. The research ID is {rid}."
    if "codeword" in q or "code word" in q:
        return facts.get("codeword") or "I don't have that information."
    if "campus" in q or "where do i study" in q or "which campus" in q:
        return facts.get("campus") or "I don't have that information."
    if "research" in q or q.endswith(" id?") or "what is my id" in q:
        return facts.get("research_id") or facts.get("id") or "I don't have that information."
    if "name" in q or "who am i" in q:
        return facts.get("name") or "I don't have that information."
    if facts:
        used = "; ".join(f"{k} = {v}" for k, v in facts.items())
        return f"From what I have saved: {used}."
    # Normal chat / unrelated questions when no matching stored facts.
    if re.search(r"\b(hi|hello|hey|thanks|thank you|ok|okay|and|what do you mean)\b", q):
        return "Happy to chat. Tell me something to remember, or ask about anything else."
    if "time" in q:
        return "I don't have a live clock here, but I can help with anything else."
    return "Sure — tell me more, or share something you want me to remember."
