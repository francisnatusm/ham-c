"""Pick a few stored facts that match the current question."""

from __future__ import annotations

import re


STOP = {
    "a", "an", "the", "is", "am", "are", "was", "were", "be", "to", "of", "and",
    "or", "in", "on", "for", "my", "i", "me", "you", "what", "which", "who",
    "do", "does", "did", "please", "tell", "about",
}


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9-]+", text.lower())
    return {w for w in words if w not in STOP and len(w) > 1}


def is_fact_question(text: str) -> bool:
    """True when the user is asking to recall a personal/project fact."""
    q = text.lower().strip()
    if not q:
        return False
    asking = bool(
        re.search(
            r"\b(what|which|where|who|whose|when's|when is|do you know|tell me|remind me)\b",
            q,
        )
        or q.endswith("?")
    )
    if not asking:
        return False
    topics = (
        r"name|codeword|code word|campus|school|university|research|"
        r"\bid\b|location|live|from|work|job|company|like|love|prefer|"
        r"favourite|favorite|project"
    )
    return bool(re.search(rf"\b({topics})\b", q) or "who am i" in q)


def retrieve(facts: list[dict], question: str, k: int = 5) -> list[dict]:
    q = tokens(question)
    if not facts:
        return []
    scored = []
    for fact in facts:
        fkey = str(fact.get("key") or fact.get("fact_key") or "")
        fval = str(fact.get("value") or "")
        if not fkey or not fval:
            continue
        key_toks = tokens(fkey)
        val_toks = tokens(fval)
        score = 0.0
        if key_toks & q:
            score += 3.0
        if val_toks & q:
            score += 2.0
        # Keep a little recency so a fresh update beats an old unused fact.
        score += 0.1
        if "campus" in q and fkey == "campus":
            score += 4.0
        if any(w in q for w in ("codeword", "code", "project")) and fkey in {
            "codeword",
            "project_codeword",
        }:
            score += 4.0
        if any(w in q for w in ("id", "research")) and fkey in {
            "research_id",
            "id",
        }:
            score += 4.0
        if "name" in q and fkey == "name":
            score += 4.0
        if any(w in q for w in ("study", "school", "university", "campus")) and fkey in {
            "school",
            "campus",
            "university",
        }:
            score += 4.0
        if any(w in q for w in ("live", "from", "location", "where")) and fkey in {
            "location",
            "city",
            "country",
        }:
            score += 4.0
        if any(w in q for w in ("like", "love", "enjoy", "prefer", "favourite", "favorite")) and fkey in {
            "like",
            "prefer",
        }:
            score += 4.0
        if any(w in q for w in ("work", "job", "company")) and fkey in {
            "work",
            "job",
            "company",
        }:
            score += 4.0
        scored.append((score, fact))
    scored.sort(key=lambda item: item[0], reverse=True)
    picked = [fact for score, fact in scored if score >= 2.0][:k]
    if not picked:
        # If nothing matches clearly, send nothing. Do not dump the whole store.
        return []
    return picked
