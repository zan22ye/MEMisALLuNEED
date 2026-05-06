from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from memisalluneed.search import MemorySearchResult


@dataclass(frozen=True)
class ResolvedMemoryContext:
    primary: list[MemorySearchResult] = field(default_factory=list)
    older_relevant: list[MemorySearchResult] = field(default_factory=list)
    unresolved_time: list[MemorySearchResult] = field(default_factory=list)


def _parse_created_at(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def resolve_current_memories(
    results: list[MemorySearchResult],
    *,
    final_k: int,
) -> ResolvedMemoryContext:
    valid: list[tuple[datetime, MemorySearchResult]] = []
    unresolved: list[MemorySearchResult] = []
    for result in results:
        created_at = _parse_created_at(result.item.created_at)
        if created_at is None:
            unresolved.append(result)
        else:
            valid.append((created_at, result))

    valid.sort(key=lambda pair: pair[0], reverse=True)
    ordered = [result for _, result in valid]

    if final_k <= 0:
        return ResolvedMemoryContext(
            older_relevant=ordered,
            unresolved_time=unresolved,
        )

    return ResolvedMemoryContext(
        primary=ordered[:final_k],
        older_relevant=ordered[final_k:],
        unresolved_time=unresolved,
    )
