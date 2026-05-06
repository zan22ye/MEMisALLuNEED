from dataclasses import replace

from memisalluneed.resolution import ResolvedMemoryContext
from memisalluneed.resolution import resolve_current_memories
from memisalluneed.schema import create_memory_item
from memisalluneed.search import MemorySearchResult


def test_resolved_memory_context_defaults_to_empty_lists():
    context = ResolvedMemoryContext()

    assert context.primary == []
    assert context.older_relevant == []
    assert context.unresolved_time == []


def make_result(content: str, created_at: str, score: float = 1.0) -> MemorySearchResult:
    item = create_memory_item(content)
    item = replace(item, created_at=created_at, updated_at=created_at)
    return MemorySearchResult(item=item, score=score)


def test_resolver_prioritizes_newer_valid_candidates():
    old = make_result("User liked vegetarian restaurants.", "2026-01-01T00:00:00+00:00")
    new = make_result("User now follows a vegan diet.", "2026-05-01T00:00:00+00:00")
    newer = make_result("User prefers quiet restaurants.", "2026-05-02T00:00:00+00:00")

    context = resolve_current_memories([old, new, newer], final_k=2)

    assert [result.item.id for result in context.primary] == [
        newer.item.id,
        new.item.id,
    ]
    assert [result.item.id for result in context.older_relevant] == [old.item.id]
    assert context.unresolved_time == []


def test_resolver_separates_invalid_timestamps():
    valid = make_result("Valid memory.", "2026-05-01T00:00:00+00:00")
    invalid = make_result("Invalid timestamp memory.", "not-a-date")

    context = resolve_current_memories([invalid, valid], final_k=5)

    assert [result.item.id for result in context.primary] == [valid.item.id]
    assert context.older_relevant == []
    assert [result.item.id for result in context.unresolved_time] == [invalid.item.id]


def test_resolver_does_not_mutate_memory_items():
    old = make_result("Old memory.", "2026-01-01T00:00:00+00:00")
    original = old.item.to_dict()

    resolve_current_memories([old], final_k=1)

    assert old.item.to_dict() == original
