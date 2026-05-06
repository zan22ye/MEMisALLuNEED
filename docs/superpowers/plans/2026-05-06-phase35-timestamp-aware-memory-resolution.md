# Phase 3.5 Timestamp-Aware Memory Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a timestamp-aware resolver layer so `mem chat` uses broad relevance candidates, then prioritizes newer relevant memories without deleting or overwriting older memories.

**Architecture:** Build this on top of the existing Phase 3 branch/worktree, not directly on `main`, because Phase 3.5 depends on `ChatRunResult`, `chat_qa` formation, and Phase 3 chat prompt behavior. Keep `mem search` unchanged. Add a small deterministic resolver module that classifies relevance candidates into `primary`, `older_relevant`, and `unresolved_time`; wire `mem chat` to search with `recall_candidate_k`, resolve candidates, and build a prompt with explicit sections.

**Tech Stack:** Python 3.11+, argparse CLI, TOML config, SQLite `MemoryStore`, deterministic keyword recall, pytest.

---

## Prerequisite Worktree

Run this plan from the existing Phase 3 worktree:

```text
/home/zan22ye/memorax/MEMisALLuNEED/.worktrees/phase3-memory-centric-qa
```

Expected branch:

```text
phase3-memory-centric-qa
```

Do not implement Phase 3.5 from `main` unless Phase 3 has already been merged.

---

## File Structure

- Create `memisalluneed/resolution.py`
  - Owns `ResolvedMemoryContext`.
  - Owns timestamp parsing and deterministic resolution.
  - Does not depend on `MemoryStore`.
- Create `tests/test_resolution.py`
  - Covers resolver behavior in isolation.
- Modify `memisalluneed/config.py`
  - Add `SessionConfig.recall_candidate_k`.
  - Load and validate `session.recall_candidate_k`.
  - Support CLI override if added in `cli.py`.
- Modify `config.example.toml`
  - Add `recall_candidate_k = 50`.
- Modify `tests/test_config.py`
  - Cover loading, override, and validation for `recall_candidate_k`.
- Modify `memisalluneed/cli.py`
  - Add optional `--recall-candidate-k`.
  - Search with `recall_candidate_k` inside `mem chat`.
  - Resolve candidate results before prompt construction.
  - Build prompt sections for primary, older relevant, and timestamp-unresolved memories.
  - Keep `mem search` unchanged.
- Modify `tests/test_chat_cli.py`
  - Cover parser option.
  - Cover prompt sections.
  - Cover broad candidate recall.
  - Cover used memory ids only for memories supplied to prompt.
- Modify `docs/roadmap.md`
  - Mark Phase 3.5 implementation status after tests pass.

---

### Task 1: Add Resolver Data Model

**Files:**
- Create: `memisalluneed/resolution.py`
- Test: `tests/test_resolution.py`

- [ ] **Step 1: Write failing resolver model test**

Create `tests/test_resolution.py`:

```python
from memisalluneed.resolution import ResolvedMemoryContext


def test_resolved_memory_context_defaults_to_empty_lists():
    context = ResolvedMemoryContext()

    assert context.primary == []
    assert context.older_relevant == []
    assert context.unresolved_time == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_resolution.py::test_resolved_memory_context_defaults_to_empty_lists -v
```

Expected: FAIL because `memisalluneed.resolution` does not exist.

- [ ] **Step 3: Create resolver module**

Create `memisalluneed/resolution.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from memisalluneed.search import MemorySearchResult


@dataclass(frozen=True)
class ResolvedMemoryContext:
    primary: list[MemorySearchResult] = field(default_factory=list)
    older_relevant: list[MemorySearchResult] = field(default_factory=list)
    unresolved_time: list[MemorySearchResult] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_resolution.py::test_resolved_memory_context_defaults_to_empty_lists -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/resolution.py tests/test_resolution.py
git commit -m "Add timestamp-aware resolution model"
```

---

### Task 2: Resolve Candidates by Timestamp

**Files:**
- Modify: `memisalluneed/resolution.py`
- Test: `tests/test_resolution.py`

- [ ] **Step 1: Add failing resolver behavior tests**

Append to `tests/test_resolution.py`:

```python
from dataclasses import replace

from memisalluneed.schema import create_memory_item
from memisalluneed.search import MemorySearchResult
from memisalluneed.resolution import resolve_current_memories


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_resolution.py::test_resolver_prioritizes_newer_valid_candidates tests/test_resolution.py::test_resolver_separates_invalid_timestamps tests/test_resolution.py::test_resolver_does_not_mutate_memory_items -v
```

Expected: FAIL because `resolve_current_memories` does not exist.

- [ ] **Step 3: Implement resolver**

Update `memisalluneed/resolution.py`:

```python
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
    if final_k <= 0:
        return ResolvedMemoryContext(
            older_relevant=[
                result
                for result in results
                if _parse_created_at(result.item.created_at) is not None
            ],
            unresolved_time=[
                result
                for result in results
                if _parse_created_at(result.item.created_at) is None
            ],
        )

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
    return ResolvedMemoryContext(
        primary=ordered[:final_k],
        older_relevant=ordered[final_k:],
        unresolved_time=unresolved,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_resolution.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/resolution.py tests/test_resolution.py
git commit -m "Resolve relevant memories by timestamp"
```

---

### Task 3: Add `recall_candidate_k` Config

**Files:**
- Modify: `memisalluneed/config.py`
- Modify: `config.example.toml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing config test**

In `tests/test_config.py`, update the existing config fixtures so every `[session]` block includes:

```toml
recall_candidate_k = 50
```

Then add:

```python
def test_load_config_reads_recall_candidate_k(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[chat_model]
provider = "openai"
model = "chat"
[formation_model]
provider = "openai"
model = "formation"
[session]
max_turns = 6
max_tokens = 100000
recall_top_k = 5
recall_candidate_k = 50
[http]
request_timeout = 60
[providers.openai]
api_key_env = "OPENAI_API_KEY"
base_url = "https://example.test/v1"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.session.recall_candidate_k == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_config.py::test_load_config_reads_recall_candidate_k -v
```

Expected: FAIL because `SessionConfig` does not expose `recall_candidate_k`.

- [ ] **Step 3: Implement config field**

In `memisalluneed/config.py`:

1. Add field to `SessionConfig`:

```python
    recall_candidate_k: int
```

2. Add field to `ConfigOverrides`:

```python
    recall_candidate_k: int | None = None
```

3. In `load_config`, set:

```python
    session = SessionConfig(
        max_turns=overrides.max_turns if overrides.max_turns is not None else session.max_turns,
        max_tokens=overrides.max_tokens if overrides.max_tokens is not None else session.max_tokens,
        recall_top_k=overrides.recall_top_k
        if overrides.recall_top_k is not None
        else session.recall_top_k,
        recall_candidate_k=overrides.recall_candidate_k
        if overrides.recall_candidate_k is not None
        else session.recall_candidate_k,
    )
```

4. Validate:

```python
    _validate_positive_int("session.recall_candidate_k", session.recall_candidate_k)
    if session.recall_candidate_k < session.recall_top_k:
        raise ValueError("session.recall_candidate_k must be greater than or equal to session.recall_top_k")
```

5. In `_load_session_config`, read:

```python
    recall_candidate_k = _required_int(raw, "recall_candidate_k", "session")
```

and return it in `SessionConfig`.

- [ ] **Step 4: Update example config**

In `config.example.toml`, add under `[session]`:

```toml
recall_candidate_k = 50
```

- [ ] **Step 5: Run config tests**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add memisalluneed/config.py config.example.toml tests/test_config.py
git commit -m "Add recall candidate pool config"
```

---

### Task 4: Add CLI Override for `recall_candidate_k`

**Files:**
- Modify: `memisalluneed/cli.py`
- Test: `tests/test_chat_cli.py`

- [ ] **Step 1: Write failing parser test**

Append to `tests/test_chat_cli.py`:

```python
def test_chat_parser_accepts_recall_candidate_k():
    parser = build_parser()

    args = parser.parse_args(["chat", "--recall-candidate-k", "50"])

    assert args.command == "chat"
    assert args.recall_candidate_k == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_chat_cli.py::test_chat_parser_accepts_recall_candidate_k -v
```

Expected: FAIL because `--recall-candidate-k` is not recognized.

- [ ] **Step 3: Add parser option and override**

In `memisalluneed/cli.py`, add near `--recall-top-k`:

```python
    chat_parser.add_argument("--recall-candidate-k", type=int)
```

Update `_config_overrides_from_args`:

```python
        recall_candidate_k=args.recall_candidate_k,
```

- [ ] **Step 4: Run parser test**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_chat_cli.py::test_chat_parser_accepts_recall_candidate_k -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Add recall candidate pool CLI override"
```

---

### Task 5: Build Resolved Memory Prompt Sections

**Files:**
- Modify: `memisalluneed/cli.py`
- Test: `tests/test_chat_cli.py`

- [ ] **Step 1: Write failing prompt section test**

Append to `tests/test_chat_cli.py`:

```python
from dataclasses import replace

from memisalluneed.resolution import ResolvedMemoryContext
from memisalluneed.search import MemorySearchResult


def memory_result(content: str, created_at: str, score: float = 1.0) -> MemorySearchResult:
    item = create_memory_item(content)
    item = replace(item, created_at=created_at, updated_at=created_at)
    return MemorySearchResult(item=item, score=score)


def test_build_chat_messages_includes_resolved_memory_sections():
    primary = memory_result("User now follows a vegan diet.", "2026-05-01T00:00:00+00:00")
    older = memory_result("User liked vegetarian restaurants.", "2026-01-01T00:00:00+00:00")
    unresolved = memory_result("User dislikes loud venues.", "not-a-date")

    messages = build_chat_messages(
        active_turns=[],
        resolved_context=ResolvedMemoryContext(
            primary=[primary],
            older_relevant=[older],
            unresolved_time=[unresolved],
        ),
        user_message="What restaurant should I recommend?",
    )

    memory_section = messages[-2]["content"]
    assert "Primary relevant memories:" in memory_section
    assert "Older relevant memories:" in memory_section
    assert "Timestamp-unresolved memories:" in memory_section
    assert "User now follows a vegan diet." in memory_section
    assert "User liked vegetarian restaurants." in memory_section
    assert "User dislikes loud venues." in memory_section
    assert "score=" not in memory_section
```

Update import at top of `tests/test_chat_cli.py`:

```python
from memisalluneed.cli import build_chat_messages
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_chat_cli.py::test_build_chat_messages_includes_resolved_memory_sections -v
```

Expected: FAIL because `build_chat_messages` does not accept `resolved_context`.

- [ ] **Step 3: Update chat message builder**

In `memisalluneed/cli.py`, import:

```python
from memisalluneed.resolution import ResolvedMemoryContext
```

Replace `build_chat_messages` signature:

```python
def build_chat_messages(
    active_turns: list[SessionTurn],
    resolved_context: ResolvedMemoryContext,
    user_message: str,
) -> list[ChatMessage]:
```

Replace recalled memory section construction with:

```python
    def format_result(result) -> str:
        item = result.item
        return (
            f"- {item.id} ({item.type}, {item.state}, "
            f"confidence={item.confidence:g}, created_at={item.created_at}): "
            f"{item.content}"
        )

    sections = ["Resolved memory context:"]
    sections.append("Primary relevant memories:")
    sections.extend(
        [format_result(result) for result in resolved_context.primary] or ["- none"]
    )
    sections.append("Older relevant memories:")
    sections.extend(
        [format_result(result) for result in resolved_context.older_relevant]
        or ["- none"]
    )
    sections.append("Timestamp-unresolved memories:")
    sections.extend(
        [format_result(result) for result in resolved_context.unresolved_time]
        or ["- none"]
    )
    messages.append({"role": "system", "content": "\n".join(sections)})
```

Update the system prompt text to include:

```python
"When primary and older relevant memories conflict, prefer primary memories. "
"Older relevant memories are still useful context but may be less current. "
"Use timestamp-unresolved memories cautiously. "
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_chat_cli.py::test_build_chat_messages_includes_resolved_memory_sections -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Build timestamp-resolved chat memory sections"
```

---

### Task 6: Wire Broad Recall and Resolver into `mem chat`

**Files:**
- Modify: `memisalluneed/cli.py`
- Test: `tests/test_chat_cli.py`

- [ ] **Step 1: Write failing broad recall test**

Append to `tests/test_chat_cli.py`:

```python
def test_run_chat_once_uses_candidate_k_and_resolved_primary_context(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    old = create_memory_item("User liked vegetarian restaurants.")
    old = replace(old, created_at="2026-01-01T00:00:00+00:00", updated_at="2026-01-01T00:00:00+00:00")
    new = create_memory_item("User now follows a vegan diet.")
    new = replace(new, created_at="2026-05-01T00:00:00+00:00", updated_at="2026-05-01T00:00:00+00:00")
    store.add(old)
    store.add(new)
    session_path = tmp_path / "session.json"
    chat_model = FakeChatModel()
    formation_model = FakeFormationModel()
    config = AppConfig(
        chat_model=ModelRoleConfig(provider="openai", model="chat"),
        formation_model=ModelRoleConfig(provider="openai", model="formation"),
        session=SessionConfig(
            max_turns=6,
            max_tokens=100000,
            recall_top_k=1,
            recall_candidate_k=2,
        ),
        http=HttpConfig(request_timeout=60),
        providers={
            "openai": ProviderConfig(
                api_key_env="OPENAI_API_KEY",
                base_url="https://example.test/v1",
            )
        },
    )

    result = run_chat_once(
        user_message="What restaurants fit the user diet?",
        config=config,
        store=store,
        session_path=session_path,
        chat_model=chat_model,
        formation_model=formation_model,
        resume=False,
    )

    memory_section = chat_model.messages[-2]["content"]
    assert "Primary relevant memories:" in memory_section
    assert "User now follows a vegan diet." in memory_section
    assert "Older relevant memories:" in memory_section
    assert "User liked vegetarian restaurants." in memory_section
    assert [memory.content for memory in result.used_memories] == [
        "User now follows a vegan diet.",
        "User liked vegetarian restaurants.",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_chat_cli.py::test_run_chat_once_uses_candidate_k_and_resolved_primary_context -v
```

Expected: FAIL because `run_chat_once` still searches with `recall_top_k` and does not resolve candidates.

- [ ] **Step 3: Wire resolver into `run_chat_once`**

In `memisalluneed/cli.py`, import:

```python
from memisalluneed.resolution import resolve_current_memories
```

Update `run_chat_once`:

```python
    recalled_results = search_memories(
        store,
        user_message,
        top_k=config.session.recall_candidate_k,
    )
    resolved_context = resolve_current_memories(
        recalled_results,
        final_k=config.session.recall_top_k,
    )
    prompt_results = (
        resolved_context.primary
        + resolved_context.older_relevant
        + resolved_context.unresolved_time
    )
    used_memories = [result.item for result in prompt_results]
    assistant_reply = chat_model.complete(
        build_chat_messages(session.turns, resolved_context, user_message)
    )
```

Update `SessionTurn` construction:

```python
        recalled_memory_ids=[memory.id for memory in used_memories],
```

- [ ] **Step 4: Run focused chat test**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_chat_cli.py::test_run_chat_once_uses_candidate_k_and_resolved_primary_context -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Use timestamp resolver in mem chat"
```

---

### Task 7: Preserve `mem search` Behavior

**Files:**
- Test: `tests/test_search.py`

- [ ] **Step 1: Add regression test**

Append to `tests/test_search.py`:

```python
from dataclasses import replace


def test_mem_search_ranking_remains_relevance_first(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    store.init()
    newer_low_relevance = create_memory_item("external")
    newer_low_relevance = replace(
        newer_low_relevance,
        created_at="2026-05-01T00:00:00+00:00",
        updated_at="2026-05-01T00:00:00+00:00",
    )
    older_high_relevance = create_memory_item("external knowledge memory insufficient")
    older_high_relevance = replace(
        older_high_relevance,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    store.add(newer_low_relevance)
    store.add(older_high_relevance)

    results = search_memories(store, "external knowledge memory insufficient", top_k=2)

    assert results[0].item.id == older_high_relevance.id
```

- [ ] **Step 2: Run regression test**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_search.py::test_mem_search_ranking_remains_relevance_first -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_search.py
git commit -m "Cover relevance-first search behavior"
```

---

### Task 8: Update Roadmap Implementation Status

**Files:**
- Modify: `docs/roadmap.md`

- [ ] **Step 1: Update Phase 3.5 status**

Under `## Phase 3.5: Timestamp-Aware Memory Resolution`, add:

```markdown
### Status

Implemented as deterministic timestamp-aware resolution for `mem chat`.
```

Keep the non-goals unchanged.

- [ ] **Step 2: Commit**

```bash
git add docs/roadmap.md
git commit -m "Document Phase 3.5 implementation status"
```

---

### Task 9: Full Regression and Acceptance

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run full test suite**

Run:

```bash
uv run --with pytest --with httpx pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Verify chat help includes both recall options**

Run:

```bash
uv run --with pytest --with httpx python -m memisalluneed.cli chat --help
```

Expected output includes:

```text
--recall-top-k
--recall-candidate-k
--show-memory-trace
```

- [ ] **Step 3: Verify no recent-only implementation exists**

Run:

```bash
rg -n "recent|recency" memisalluneed tests
```

Expected: no implementation of recent-only candidate retrieval. Mentions in docs are allowed, but not in runtime code except comments/tests that explicitly assert it is not implemented.

- [ ] **Step 4: Verify no embedding/vector implementation was added**

Run:

```bash
rg -n "embedding|vector" memisalluneed tests
```

Expected: no runtime implementation.

- [ ] **Step 5: Verify worktree is clean**

Run:

```bash
git status --short
```

Expected: no output.

---

## Self-Review Checklist

- [ ] Implementation is based on Phase 3 branch/worktree.
- [ ] `mem search` behavior is unchanged.
- [ ] No recent-only candidate channel is added.
- [ ] Resolver receives only relevance candidates.
- [ ] Resolver uses `created_at` only after relevance recall.
- [ ] Resolver outputs `primary`, `older_relevant`, and `unresolved_time`.
- [ ] Resolver does not mutate memory items or delete stored memories.
- [ ] `mem chat` uses `recall_candidate_k` for broad recall.
- [ ] `mem chat` uses `recall_top_k` as the primary final context size.
- [ ] Chat prompt distinguishes primary, older relevant, and timestamp-unresolved memories.
- [ ] No external search, embeddings, vector database, graph reasoning, or automatic contradiction detection is added.

