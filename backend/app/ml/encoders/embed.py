from functools import lru_cache


@lru_cache
def _get_model():
    # expensive import deferred to first call
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


def embed_text(text: str) -> list[float]:
    """Returns a 384-dim vector in the same space as track embeddings."""
    return _get_model().encode(text).tolist()
