"""
RAG (Retrieval-Augmented Generation) for official tax provisions.
Loads data/official_provisions.md, chunks by sections, and retrieves relevant text for LLM context.
"""

import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
PROVISIONS_FILE = DATA_DIR / "official_provisions.md"

_chunks_cache: list[dict] | None = None


def _load_and_chunk() -> list[dict]:
    """Load provisions file and split into chunks (by ## header or paragraph)."""
    global _chunks_cache
    if _chunks_cache is not None:
        return _chunks_cache

    if not PROVISIONS_FILE.exists():
        _chunks_cache = []
        return _chunks_cache

    text = PROVISIONS_FILE.read_text(encoding="utf-8")
    chunks = []
    # Split by ## or ### headers
    parts = re.split(r"\n(?=##\s)", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # First line as title
        lines = part.split("\n")
        title = lines[0].lstrip("#").strip() if lines else "Section"
        content = "\n".join(lines).strip()
        chunks.append({"title": title, "content": content, "text": content})

    _chunks_cache = chunks
    return chunks


def _score_chunk(chunk: dict, query: str) -> float:
    """Simple keyword relevance: count of query tokens in chunk (case-insensitive)."""
    q = query.lower().strip()
    if not q:
        return 0
    tokens = set(re.split(r"\s+", q))
    text = (chunk.get("content") or chunk.get("text") or "").lower()
    return sum(1 for t in tokens if t in text and len(t) > 1)


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Return top_k most relevant chunks for the query (for RAG context)."""
    chunks = _load_and_chunk()
    if not chunks:
        return []
    scored = [(c, _score_chunk(c, query)) for c in chunks]
    scored.sort(key=lambda x: -x[1])
    return [c for c, _ in scored[:top_k]]


def get_full_context() -> str:
    """Return full provisions text for fallback or when no specific query."""
    if not PROVISIONS_FILE.exists():
        return ""
    return PROVISIONS_FILE.read_text(encoding="utf-8").strip()


def format_chunks_for_prompt(chunks: list[dict]) -> str:
    """Format retrieved chunks as a single string for LLM system/user context."""
    if not chunks:
        return get_full_context()
    return "\n\n---\n\n".join(
        f"## {c.get('title', '')}\n{c.get('content', c.get('text', ''))}" for c in chunks
    )
