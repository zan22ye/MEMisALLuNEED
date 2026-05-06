from __future__ import annotations

from dataclasses import dataclass, field

from memisalluneed.search import MemorySearchResult


@dataclass(frozen=True)
class ResolvedMemoryContext:
    primary: list[MemorySearchResult] = field(default_factory=list)
    older_relevant: list[MemorySearchResult] = field(default_factory=list)
    unresolved_time: list[MemorySearchResult] = field(default_factory=list)
