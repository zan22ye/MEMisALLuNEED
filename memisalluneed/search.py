from __future__ import annotations

import re
from dataclasses import dataclass

from memisalluneed.schema import MemoryItem
from memisalluneed.store import MemoryStore


@dataclass(frozen=True)
class MemorySearchResult:
    item: MemoryItem
    score: float


def tokenize(text: str) -> set[str]:
    return {token for token in re.split(r"\W+", text.lower()) if token}


def score_memory(query: str, item: MemoryItem) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0

    memory_tokens = tokenize(item.content)
    return len(query_tokens & memory_tokens) / len(query_tokens)


def search_memories(
    store: MemoryStore,
    query: str,
    top_k: int = 5,
) -> list[MemorySearchResult]:
    results = [
        MemorySearchResult(item=item, score=score_memory(query, item=item))
        for item in store.all()
    ]
    results = [result for result in results if result.score > 0]
    results.sort(
        key=lambda result: (
            result.score,
            result.item.confidence,
            result.item.created_at,
        ),
        reverse=True,
    )
    results = results[:top_k]
    store.mark_recalled(result.item.id for result in results)
    return results
