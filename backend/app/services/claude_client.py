from dataclasses import dataclass
from functools import lru_cache

from app.core.config import settings
from app.models import Track

_MODEL = "claude-haiku-4-5"
_JUDGE_MODEL = "claude-sonnet-5"

_JUDGE_SYSTEM_PROMPT = (
    "You are picking tracks for a listener's requested playlist. You will be given the "
    "listener's request and a numbered list of candidate tracks with their genre and tag "
    "metadata. Select the tracks that genuinely fit the mood, energy, and genre implied by "
    "the request, ordered best-fit first - use your own knowledge of what these tracks and "
    "genres actually sound like, not just keyword overlap with the tags. Exclude tracks that "
    "don't fit even if their tags loosely match. Return at most {limit} tracks; if "
    "fewer genuinely fit, return fewer rather than padding with weak matches. Respond with "
    "ONLY a comma-separated list of the selected track numbers in ranked order, nothing else."
)

_SYSTEM_PROMPT = (
    "You analyze short music playlist prompts for a semantic search system. "
    "Respond in exactly two lines, nothing else.\n"
    "Line 1: a one-to-two sentence expansion of the prompt describing mood, energy, tempo, "
    "and likely genres - the kind of detail that would appear in music reviews or tags. "
    "Do not mention specific artists or songs.\n"
    "Line 2: 3-6 lowercase, comma-separated keywords describing mood, activity, or energy "
    "level implied by the prompt (e.g. energetic, workout, chill, romantic, late-night)."
)


@dataclass
class QueryIntent:
    expanded_text: str
    keywords: list[str]


@lru_cache
def _get_client():
    from anthropic import Anthropic
    return Anthropic(api_key=settings.anthropic_api_key)


def _parse_response(text: str, fallback_prompt: str) -> QueryIntent:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        return QueryIntent(expanded_text=lines[0] if lines else fallback_prompt, keywords=[])

    expanded_text = lines[0]
    keywords = [k.strip().lower() for k in lines[1].split(",") if k.strip()]
    return QueryIntent(expanded_text=expanded_text, keywords=keywords)


def analyze_prompt(prompt: str) -> QueryIntent:
    """Expand a user's playlist prompt and extract mood/activity keywords"""
    try:
        response = _get_client().messages.create(
            model=_MODEL,
            max_tokens=250,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next((block.text for block in response.content if block.type == "text"), "")
        return _parse_response(text, prompt) if text else QueryIntent(prompt, [])
    except Exception:
        return QueryIntent(expanded_text=prompt, keywords=[])


def _describe_track(track: Track) -> str:
    genres = ", ".join(track.genres or [])
    tags = ", ".join(track.tags or [])
    return f"{track.title} by {track.artist}. Genres: {genres}. Tags: {tags}"


def _parse_selection(text: str, n_candidates: int, limit: int) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for chunk in text.strip().split(","):
        chunk = chunk.strip()
        if not chunk.isdigit():
            continue
        idx = int(chunk) - 1  # candidates are presented 1-indexed
        if 0 <= idx < n_candidates and idx not in seen:
            seen.add(idx)
            ordered.append(idx)
        if len(ordered) >= limit:
            break
    return ordered


def select_best_tracks(
    prompt: str, candidates: list[tuple[Track, float]], limit: int
) -> list[tuple[Track, float]] | None:
    candidate_list = "\n".join(
        f"{i}. {_describe_track(track)}" for i, (track, _score) in enumerate(candidates, start=1)
    )
    user_message = f"Request: {prompt}\n\nCandidates:\n{candidate_list}"

    try:
        response = _get_client().messages.create(
            model=_JUDGE_MODEL,
            max_tokens=1024,
            system=_JUDGE_SYSTEM_PROMPT.format(limit=limit),
            messages=[{"role": "user", "content": user_message}],
        )
        text = next((block.text for block in response.content if block.type == "text"), "")
        if not text:
            return None

        selection = _parse_selection(text, len(candidates), limit)
        return [candidates[i] for i in selection] or None
    except Exception:
        return None
