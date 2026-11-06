"""Scan each message for lasting facts, then save or replace them."""

from __future__ import annotations

import json
import re

from hamc.chatgpt import ChatGPTClient


CODEWORD = re.compile(
    r"(?:project\s+)?codeword\s+is\s+([A-Za-z0-9-]+)",
    re.IGNORECASE,
)
CAMPUS = re.compile(
    r"(?:study|studying|campus)\s+(?:at\s+)?(campus\s+(?:north|south|east|west)|[\w\s]+campus)",
    re.IGNORECASE,
)
TRANSFER = re.compile(
    r"transferred?.*?to\s+(campus\s+\w+)",
    re.IGNORECASE,
)
RESEARCH_ID = re.compile(
    r"(?:research\s+id|temporary\s+research\s+id)\s+(?:is\s+)?([A-Za-z0-9-]+)",
    re.IGNORECASE,
)
NAME = re.compile(
    r"(?:my\s+name\s+is|i\s+am|i'm)\s+([A-Za-z][A-Za-z'-]{1,40})",
    re.IGNORECASE,
)
SCHOOL = re.compile(
    r"(?:i\s+)?(?:study|studying|go\s+to)\s+(?:at|in)\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
LOCATION = re.compile(
    r"(?:i\s+)?(?:live|currently\s+live)\s+(?:in|at)\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
FROM = re.compile(
    r"(?:i(?:'m|\s+am)?)\s+from\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
WORK = re.compile(
    r"(?:i\s+)?work(?:s)?\s+(?:at|for|in)\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
GROUP = re.compile(
    r"(?:i(?:'m|\s+am)?\s+in\s+)?group\s+(\d+|[A-Za-z0-9]+)",
    re.IGNORECASE,
)
PREFER = re.compile(
    r"i\s+prefer\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
LIKE = re.compile(
    r"i\s+(?:also\s+)?(?:like|love|enjoy)\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
PLAY = re.compile(
    r"i\s+(?:also\s+)?play\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
SPEAK = re.compile(
    r"i\s+(?:also\s+)?speak\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
MOVED = re.compile(
    r"i\s+(?:just\s+)?moved\s+to\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
NOW_LIVE = re.compile(
    r"now\s+i\s+(?:live|stay)\s+(?:in|at)\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
NOW_STUDY = re.compile(
    r"now\s+i\s+study\s+(?:at|in)\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
MAJOR = re.compile(
    r"(?:my\s+)?major\s+is\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
MY_IS = re.compile(
    r"my\s+([a-z][a-z\s-]{1,30}?)\s+is\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
REMEMBER_IS = re.compile(
    r"remember(?:\s+that)?\s+(?:my\s+)?([a-z][\w\s-]{1,40})\s+(?:is|=)\s+(.+)$",
    re.IGNORECASE,
)
NOT_A_NAME = {
    "a", "an", "the", "here", "going", "studying", "from", "in", "at", "on",
    "not", "so", "just", "trying", "using", "looking", "asking", "student",
    "doing", "working", "living",
}
SKIP_MY_KEYS = {
    "name", "question", "message", "answer", "point",
}
CANON = {
    "university": "school",
    "college": "school",
    "uni": "school",
    "city": "location",
    "country": "location",
    "hometown": "location",
    "workplace": "work",
    "job": "work",
    "company": "work",
    "preference": "prefer",
    "like": "like",
    "love": "like",
    "enjoy": "like",
}


def _clean(value: str) -> str:
    value = value.strip().rstrip(".,;:!")
    value = re.sub(r"\s+", " ", value)
    return value


def _add(found: list[dict], key: str, value: str, confirmed: bool = True) -> None:
    key = CANON.get(key.strip().lower().replace(" ", "_"), key.strip().lower().replace(" ", "_"))
    value = _clean(value)
    if not key or not value or len(value) < 2:
        return
    if value.lower() in {"it", "this", "that", "here", "there"}:
        return
    for item in found:
        if item["key"] == key:
            item["value"] = value
            item["confirmed"] = confirmed or item["confirmed"]
            return
    found.append({"key": key, "value": value, "confirmed": confirmed})


def local_facts(text: str) -> list[dict]:
    if "?" in text and not re.search(r"\bremember\b", text, re.IGNORECASE):
        return []
    found: list[dict] = []
    confirmed = bool(re.search(r"\bremember\b", text, re.IGNORECASE))

    m = CODEWORD.search(text)
    if m:
        _add(found, "codeword", m.group(1), confirmed)
    m = TRANSFER.search(text) or CAMPUS.search(text)
    if m:
        _add(found, "campus", m.group(1).title(), confirmed)
    m = RESEARCH_ID.search(text)
    if m:
        _add(found, "research_id", m.group(1), True)
    # Skip REMEMBER_IS when research_id already captured (avoids duplicate
    # "the_temporary_research_id" for "Remember the temporary research ID is …")
    skip_remember = any(f["key"] == "research_id" for f in found)
    m = NAME.search(text)
    if m:
        name = m.group(1).strip()
        if name.lower() not in NOT_A_NAME:
            _add(found, "name", name, True)
    m = NOW_STUDY.search(text) or SCHOOL.search(text)
    if m and not any(f["key"] == "campus" for f in found):
        _add(found, "school", m.group(1), True)
    m = NOW_LIVE.search(text) or MOVED.search(text) or LOCATION.search(text)
    if m:
        _add(found, "location", m.group(1), True)
    m = FROM.search(text)
    if m and not any(f["key"] == "location" for f in found):
        _add(found, "location", m.group(1), True)
    m = WORK.search(text)
    if m:
        _add(found, "work", m.group(1), True)
    m = GROUP.search(text)
    if m:
        _add(found, "group", m.group(1), True)
    m = PREFER.search(text) or LIKE.search(text)
    if m:
        _add(found, "like", m.group(1), True)
    m = PLAY.search(text)
    if m:
        _add(found, "play", m.group(1), True)
    m = SPEAK.search(text)
    if m:
        _add(found, "speak", m.group(1), True)
    m = MAJOR.search(text)
    if m:
        _add(found, "major", m.group(1), True)
    if not skip_remember:
        m = REMEMBER_IS.search(text) or MY_IS.search(text)
        if m:
            key = m.group(1).strip().lower().replace(" ", "_")
            if key not in SKIP_MY_KEYS and "research_id" not in key:
                _add(found, key, m.group(2), True)
    return found


def _parse_facts_json(raw: str) -> list[dict]:
    """Accept raw JSON or markdown-fenced JSON from the model."""
    text = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    data = json.loads(text)
    out: list[dict] = []
    for item in data.get("facts", []):
        _add(
            out,
            str(item.get("key", "")),
            str(item.get("value", "")),
            False,
        )
    return out


def extract_facts(text: str, client: ChatGPTClient) -> list[dict]:
    found = local_facts(text)
    if found or not client.available:
        return found
    raw = client.complete(
        [
            {
                "role": "system",
                "content": (
                    "List lasting personal facts from the user message as JSON: "
                    '{"facts":[{"key":"short_label","value":"text"}]}. '
                    "Use stable keys (name, school, location, work, group, prefer, major). "
                    "If the user updates an old fact, return only the new value. "
                    "If none, return {\"facts\":[]}."
                ),
            },
            {"role": "user", "content": text},
        ],
        max_tokens=200,
    )
    try:
        return _parse_facts_json(raw)
    except (json.JSONDecodeError, TypeError, AttributeError):
        return found
