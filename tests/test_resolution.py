from memisalluneed.resolution import ResolvedMemoryContext


def test_resolved_memory_context_defaults_to_empty_lists():
    context = ResolvedMemoryContext()

    assert context.primary == []
    assert context.older_relevant == []
    assert context.unresolved_time == []
