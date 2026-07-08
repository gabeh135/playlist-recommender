from functools import lru_cache

from app.core.config import settings

_MODEL = "claude-haiku-4-5"

_SYSTEM_PROMPT = (
    "You expand short music playlist prompts into richer descriptions for semantic search. "
    "Given a short prompt, write one or two sentences describing the mood, energy, tempo, and "
    "likely genres - the kind of detail that would appear in music reviews or tags. Do not "
    "mention specific artists or songs. Respond with only the expanded description."
)

_NAMING_SYSTEM_PROMPT = (
    "You name a music playlist from a short sample of its tracks. Respond with ONLY the name "
    "- no quotes, no explanation. Keep it short (2-5 words) and evocative of the mood or genre "
    "the tracks share, not just a literal genre label."
)


@lru_cache
def _get_client():
    from anthropic import Anthropic
    return Anthropic(api_key=settings.anthropic_api_key)


def expand_query(prompt: str) -> str:
    """Expand a user prompt into a richer description"""
    try:
        response = _get_client().messages.create(
            model=_MODEL,
            max_tokens=200,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next((block.text for block in response.content if block.type == "text"), "")
        return text.strip() or prompt
    except Exception:
        return prompt


def name_playlist(track_titles: list[str]) -> str | None:
    if not track_titles:
        return None
    try:
        response = _get_client().messages.create(
            model=_MODEL,
            max_tokens=30,
            system=_NAMING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": "\n".join(track_titles)}],
        )
        text = next((block.text for block in response.content if block.type == "text"), "")
        return text.strip().strip('"') or None
    except Exception:
        return None
