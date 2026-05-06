# Phase 3 Memory-Centric QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 3 memory-centric QA behavior inside `mem chat` according to `docs/phase3-spec.md`.

**Architecture:** Keep `mem chat` as the only QA entry point. Extend the existing Phase 2 chat/session/formation flow so each answer can use recalled memories, optional trace output displays the recalled memories treated as used, and every rolled/flushed turn is formed as a single `chat_qa` payload with trace metadata. Do not add external search, vector storage, graph reasoning, or immediate per-answer memory writes.

**Tech Stack:** Python 3.11+, argparse CLI, SQLite `MemoryStore`, JSON session file, OpenAI-compatible chat model adapter, pytest.

---

## File Structure

- Modify `memisalluneed/cli.py`
  - Add `--show-memory-trace`.
  - Return both assistant reply and recalled memory trace from `run_chat_once`.
  - Print trace only when requested.
  - Pass `session_id` and per-turn recalled memories into formation.
  - Flush exit turns one by one.
- Modify `memisalluneed/formation.py`
  - Replace Phase 2 `rolling` / `exit_flush` payload builders with Phase 3 `chat_qa` payload builder.
  - Include `session_id`, turn fields, recalled memory fields, and `used_memory_ids`.
  - Update formation prompt to require `experience` memory, trace metadata, and no `source` memories.
  - Filter out `source` candidates for `chat_qa`.
- Modify `tests/test_chat_cli.py`
  - Add CLI parser and output tests for `--show-memory-trace`.
  - Update existing chat orchestration tests for the new return shape.
  - Add exit flush one-turn-at-a-time test.
- Modify `tests/test_formation.py`
  - Add `chat_qa` payload tests.
  - Add metadata and source filtering tests.
- Modify `docs/roadmap.md`
  - Mark Phase 3 as implemented only after code and tests pass.

---

### Task 1: Add Memory Trace CLI Contract

**Files:**
- Modify: `memisalluneed/cli.py`
- Test: `tests/test_chat_cli.py`

- [ ] **Step 1: Write the failing parser test**

Append to `tests/test_chat_cli.py`:

```python
def test_chat_parser_accepts_show_memory_trace():
    parser = build_parser()

    args = parser.parse_args(["chat", "--show-memory-trace"])

    assert args.command == "chat"
    assert args.show_memory_trace is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_chat_cli.py::test_chat_parser_accepts_show_memory_trace -v
```

Expected: FAIL because `--show-memory-trace` is not recognized.

- [ ] **Step 3: Add parser flag**

In `memisalluneed/cli.py`, add this near the other `chat_parser` options:

```python
    chat_parser.add_argument(
        "--show-memory-trace",
        action="store_true",
        help="Print the memories used after each assistant reply.",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_chat_cli.py::test_chat_parser_accepts_show_memory_trace -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Add Phase 3 memory trace CLI flag"
```

---

### Task 2: Return and Format Used Memory Trace

**Files:**
- Modify: `memisalluneed/cli.py`
- Test: `tests/test_chat_cli.py`

- [ ] **Step 1: Write failing trace formatting tests**

Append to `tests/test_chat_cli.py`:

```python
from memisalluneed.cli import format_memory_trace


def test_format_memory_trace_lists_used_memories():
    item = create_memory_item(
        "Phase 3 uses recalled memory.",
        memory_type="knowledge",
        state="success",
        confidence=0.75,
    )

    trace = format_memory_trace([item])

    assert trace == (
        "Used memories:\n"
        f"- {item.id} knowledge success confidence=0.75"
    )


def test_format_memory_trace_handles_no_memories():
    assert format_memory_trace([]) == "Used memories:\n- none"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_chat_cli.py::test_format_memory_trace_lists_used_memories tests/test_chat_cli.py::test_format_memory_trace_handles_no_memories -v
```

Expected: FAIL because `format_memory_trace` does not exist.

- [ ] **Step 3: Implement trace formatter**

Add to `memisalluneed/cli.py` after `_print_item`:

```python
def format_memory_trace(used_memories) -> str:
    if not used_memories:
        return "Used memories:\n- none"

    lines = [
        "Used memories:",
        *[
            (
                f"- {memory.id} {memory.type} {memory.state} "
                f"confidence={memory.confidence:g}"
            )
            for memory in used_memories
        ],
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/test_chat_cli.py::test_format_memory_trace_lists_used_memories tests/test_chat_cli.py::test_format_memory_trace_handles_no_memories -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Format Phase 3 used memory trace"
```

---

### Task 3: Preserve Used Memories in One-Turn Chat Result

**Files:**
- Modify: `memisalluneed/cli.py`
- Test: `tests/test_chat_cli.py`

- [ ] **Step 1: Update chat orchestration test for result object**

In `tests/test_chat_cli.py`, update the import:

```python
from memisalluneed.cli import ChatRunResult
```

Then update `test_run_chat_once_recalls_memory_and_rolls` so the assertion block becomes:

```python
    result = run_chat_once(
        user_message="How does Phase 2 use memory?",
        config=config,
        store=store,
        session_path=session_path,
        chat_model=chat_model,
        formation_model=formation_model,
        resume=False,
    )

    assert isinstance(result, ChatRunResult)
    assert result.assistant_reply == "assistant reply using memory"
    assert len(result.used_memories) == 1
    assert result.used_memories[0].content == "Phase 2 uses memory during chat."
    assert "Phase 2 uses memory during chat." in chat_model.messages[-2]["content"]
    assert formation_model.calls == 1
    assert any(item.content == "Rolled chat became memory." for item in store.all())
```

Remove the old `reply = ...` and `assert reply == ...` lines from that test.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_chat_cli.py::test_run_chat_once_recalls_memory_and_rolls -v
```

Expected: FAIL because `ChatRunResult` does not exist and `run_chat_once` returns a string.

- [ ] **Step 3: Add result dataclass and return used memories**

In `memisalluneed/cli.py`, add import:

```python
from dataclasses import dataclass
```

Add after `_print_item`:

```python
@dataclass(frozen=True)
class ChatRunResult:
    assistant_reply: str
    used_memories: list
```

Update `run_chat_once` return annotation:

```python
) -> ChatRunResult:
```

Inside `run_chat_once`, after `recalled_results = search_memories(...)`, add:

```python
    used_memories = [result.item for result in recalled_results]
```

At the end of `run_chat_once`, replace:

```python
    return assistant_reply
```

with:

```python
    return ChatRunResult(
        assistant_reply=assistant_reply,
        used_memories=used_memories,
    )
```

- [ ] **Step 4: Update interactive print path**

In `_run_interactive_chat`, replace:

```python
        reply = run_chat_once(
            user_message=user_message,
            config=config,
            store=store,
            session_path=session_path,
            chat_model=chat_model,
            formation_model=formation_model,
            resume=resume,
        )
        resume = True
        print(reply)
```

with:

```python
        result = run_chat_once(
            user_message=user_message,
            config=config,
            store=store,
            session_path=session_path,
            chat_model=chat_model,
            formation_model=formation_model,
            resume=resume,
        )
        resume = True
        print(result.assistant_reply)
        if args.show_memory_trace:
            print(format_memory_trace(result.used_memories))
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
pytest tests/test_chat_cli.py::test_run_chat_once_recalls_memory_and_rolls -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Return Phase 3 chat trace data"
```

---

### Task 4: Build Phase 3 `chat_qa` Formation Payload

**Files:**
- Modify: `memisalluneed/formation.py`
- Test: `tests/test_formation.py`

- [ ] **Step 1: Write failing payload test**

Append to `tests/test_formation.py`:

```python
import json

from memisalluneed.formation import build_chat_qa_payload
from memisalluneed.schema import create_memory_item


def test_build_chat_qa_payload_includes_trace_metadata():
    memory = create_memory_item(
        "The project uses bounded active session context.",
        memory_type="knowledge",
        state="success",
        confidence=0.8,
    )
    turn = SessionTurn(
        id="turn-1",
        user_message="How should chat answer?",
        assistant_message="Use bounded context plus recalled memory.",
        recalled_memory_ids=[memory.id],
        created_at="2026-05-06T00:00:00+00:00",
    )

    payload = build_chat_qa_payload(
        session_id="session-1",
        turn=turn,
        recalled_memories=[memory],
    )

    assert payload == {
        "formation_kind": "chat_qa",
        "session_id": "session-1",
        "turn": {
            "id": "turn-1",
            "user_message": "How should chat answer?",
            "assistant_message": "Use bounded context plus recalled memory.",
            "created_at": "2026-05-06T00:00:00+00:00",
        },
        "recalled_memories": [
            {
                "id": memory.id,
                "type": "knowledge",
                "state": "success",
                "confidence": 0.8,
                "content": "The project uses bounded active session context.",
            }
        ],
        "used_memory_ids": [memory.id],
    }
    assert "score" not in json.dumps(payload)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_formation.py::test_build_chat_qa_payload_includes_trace_metadata -v
```

Expected: FAIL because `build_chat_qa_payload` does not exist.

- [ ] **Step 3: Implement `build_chat_qa_payload`**

In `memisalluneed/formation.py`, replace `build_rolling_payload` with:

```python
def build_chat_qa_payload(
    *,
    session_id: str,
    turn: SessionTurn,
    recalled_memories: list[MemoryItem],
) -> dict[str, Any]:
    return {
        "formation_kind": "chat_qa",
        "session_id": session_id,
        "turn": {
            "id": turn.id,
            "user_message": turn.user_message,
            "assistant_message": turn.assistant_message,
            "created_at": turn.created_at,
        },
        "recalled_memories": [
            {
                "id": memory.id,
                "type": memory.type,
                "state": memory.state,
                "confidence": memory.confidence,
                "content": memory.content,
            }
            for memory in recalled_memories
        ],
        "used_memory_ids": [memory.id for memory in recalled_memories],
    }
```

Delete `build_exit_flush_payload`; Phase 3 flushes one turn at a time.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_formation.py::test_build_chat_qa_payload_includes_trace_metadata -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/formation.py tests/test_formation.py
git commit -m "Build Phase 3 chat QA formation payloads"
```

---

### Task 5: Form Rolled Turns as `chat_qa`

**Files:**
- Modify: `memisalluneed/formation.py`
- Modify: `memisalluneed/cli.py`
- Test: `tests/test_formation.py`
- Test: `tests/test_chat_cli.py`

- [ ] **Step 1: Write failing formation service test**

Append to `tests/test_formation.py`:

```python
def test_form_from_chat_qa_turn_sends_chat_qa_payload(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    recalled = create_memory_item(
        "Phase 3 turns preserve recall traces.",
        memory_type="knowledge",
    )
    store.add(recalled)
    model = FakeFormationModel(
        """
{"memories":[{"type":"experience","content":"The QA turn used recalled memory.","state":"success","confidence":0.8,"metadata":{"source":"chat_session","formation_kind":"chat_qa","session_id":"session-1","turn_id":"turn-1","recalled_memory_ids":["REPLACED"],"used_memory_ids":["REPLACED"]}}]}
""".strip().replace("REPLACED", recalled.id)
    )
    service = FormationService(model=model, store=store)
    turn = SessionTurn(
        id="turn-1",
        user_message="What changed in Phase 3?",
        assistant_message="It preserves QA recall trace metadata.",
        recalled_memory_ids=[recalled.id],
        created_at="2026-05-06T00:00:00+00:00",
    )

    written = service.form_from_chat_qa_turn(
        session_id="session-1",
        turn=turn,
        recalled_memories=[recalled],
    )

    payload = json.loads(model.messages[1]["content"])
    assert payload["formation_kind"] == "chat_qa"
    assert payload["session_id"] == "session-1"
    assert payload["used_memory_ids"] == [recalled.id]
    assert len(written) == 1
    assert written[0].type == "experience"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_formation.py::test_form_from_chat_qa_turn_sends_chat_qa_payload -v
```

Expected: FAIL because `form_from_chat_qa_turn` does not exist.

- [ ] **Step 3: Implement service method**

In `memisalluneed/formation.py`, replace `form_from_rolled_turn` and `form_from_exit_flush` with:

```python
    def form_from_chat_qa_turn(
        self,
        *,
        session_id: str,
        turn: SessionTurn,
        recalled_memories: list[MemoryItem],
    ) -> list[MemoryItem]:
        payload = build_chat_qa_payload(
            session_id=session_id,
            turn=turn,
            recalled_memories=recalled_memories,
        )
        return self._form_and_write(payload)
```

- [ ] **Step 4: Update `run_chat_once` rolling formation**

In `memisalluneed/cli.py`, replace:

```python
        formation.form_from_rolled_turn(
            rolled_turn,
            recalled_memories=recalled_memories,
        )
```

with:

```python
        formation.form_from_chat_qa_turn(
            session_id=session.session_id,
            turn=rolled_turn,
            recalled_memories=recalled_memories,
        )
```

- [ ] **Step 5: Update fake formation response in chat test**

In `tests/test_chat_cli.py`, change `FakeFormationModel.complete` to return `formation_kind` `"chat_qa"` and type `"experience"`:

```python
    def complete(self, messages):
        self.calls += 1
        return '{"memories":[{"type":"experience","content":"Rolled chat became memory.","state":"success","confidence":0.7,"metadata":{"source":"chat_session","formation_kind":"chat_qa","session_id":"session","turn_id":"turn","recalled_memory_ids":[],"used_memory_ids":[]}}]}'
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
pytest tests/test_formation.py::test_form_from_chat_qa_turn_sends_chat_qa_payload tests/test_chat_cli.py::test_run_chat_once_recalls_memory_and_rolls -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add memisalluneed/formation.py memisalluneed/cli.py tests/test_formation.py tests/test_chat_cli.py
git commit -m "Form rolled chat turns as QA memories"
```

---

### Task 6: Flush Exit Turns One by One

**Files:**
- Modify: `memisalluneed/cli.py`
- Test: `tests/test_chat_cli.py`

- [ ] **Step 1: Write failing exit flush granularity test**

Append to `tests/test_chat_cli.py`:

```python
from memisalluneed.cli import flush_session_on_exit
from memisalluneed.session import SessionState, SessionTurn


class RecordingFormationModel:
    def __init__(self):
        self.payloads = []

    def complete(self, messages):
        import json

        payload = json.loads(messages[1]["content"])
        self.payloads.append(payload)
        turn_id = payload["turn"]["id"]
        return (
            '{"memories":[{"type":"experience","content":"Flushed '
            + turn_id
            + '","state":"success","confidence":0.8,"metadata":{"source":"chat_session","formation_kind":"chat_qa","session_id":"'
            + payload["session_id"]
            + '","turn_id":"'
            + turn_id
            + '","recalled_memory_ids":[],"used_memory_ids":[]}}]}'
        )


def test_flush_session_on_exit_forms_each_turn_individually(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    session_path = tmp_path / "session.json"
    session = SessionState.new()
    session.session_id = "session-1"
    session.turns = [
        SessionTurn(
            id="turn-1",
            user_message="first",
            assistant_message="reply one",
            recalled_memory_ids=[],
            created_at="2026-05-06T00:00:00+00:00",
        ),
        SessionTurn(
            id="turn-2",
            user_message="second",
            assistant_message="reply two",
            recalled_memory_ids=[],
            created_at="2026-05-06T00:01:00+00:00",
        ),
    ]
    session.save(session_path)
    model = RecordingFormationModel()

    written = flush_session_on_exit(session_path, model, store)

    assert [payload["turn"]["id"] for payload in model.payloads] == ["turn-1", "turn-2"]
    assert all(payload["formation_kind"] == "chat_qa" for payload in model.payloads)
    assert len(written) == 2
    assert not session_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_chat_cli.py::test_flush_session_on_exit_forms_each_turn_individually -v
```

Expected: FAIL because current exit flush sends all turns in one payload.

- [ ] **Step 3: Implement one-turn exit flush**

In `memisalluneed/cli.py`, replace `flush_session_on_exit` with:

```python
def flush_session_on_exit(
    session_path: str | Path,
    formation_model: ChatModel,
    store: MemoryStore,
) -> list:
    session = SessionState.load(session_path)
    if not session.turns:
        session.clear_file(session_path)
        return []

    formation = FormationService(model=formation_model, store=store)
    written = []
    for turn in session.turns:
        recalled_memories = [
            memory
            for memory_id in turn.recalled_memory_ids
            if (memory := store.get(memory_id)) is not None
        ]
        written.extend(
            formation.form_from_chat_qa_turn(
                session_id=session.session_id,
                turn=turn,
                recalled_memories=recalled_memories,
            )
        )
    session.clear_file(session_path)
    return written
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_chat_cli.py::test_flush_session_on_exit_forms_each_turn_individually -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Flush Phase 3 chat turns individually"
```

---

### Task 7: Enforce Phase 3 Formation Output Rules

**Files:**
- Modify: `memisalluneed/formation.py`
- Test: `tests/test_formation.py`

- [ ] **Step 1: Write failing source filtering test**

Append to `tests/test_formation.py`:

```python
def test_chat_qa_formation_does_not_write_source_memories(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    model = FakeFormationModel(
        """
{"memories":[{"type":"source","content":"External source text should not be stored in Phase 3.","state":"success","confidence":0.9,"metadata":{"source":"chat_session","formation_kind":"chat_qa","session_id":"session-1","turn_id":"turn-1","recalled_memory_ids":[],"used_memory_ids":[]}},{"type":"experience","content":"The QA turn became reusable experience.","state":"success","confidence":0.9,"metadata":{"source":"chat_session","formation_kind":"chat_qa","session_id":"session-1","turn_id":"turn-1","recalled_memory_ids":[],"used_memory_ids":[]}}]}
""".strip()
    )
    service = FormationService(model=model, store=store)
    turn = SessionTurn(
        id="turn-1",
        user_message="question",
        assistant_message="answer",
        recalled_memory_ids=[],
        created_at="2026-05-06T00:00:00+00:00",
    )

    written = service.form_from_chat_qa_turn(
        session_id="session-1",
        turn=turn,
        recalled_memories=[],
    )

    assert [memory.type for memory in written] == ["experience"]
    assert [memory.type for memory in store.all()] == ["experience"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_formation.py::test_chat_qa_formation_does_not_write_source_memories -v
```

Expected: FAIL because `source` candidates are currently valid and written.

- [ ] **Step 3: Filter `source` memories for `chat_qa` payloads**

In `memisalluneed/formation.py`, update `_form_and_write`:

```python
    def _form_and_write(self, payload: dict[str, Any]) -> list[MemoryItem]:
        raw_response = self.model.complete(build_formation_messages(payload))
        memories = parse_memory_candidates(raw_response)
        if payload.get("formation_kind") == "chat_qa":
            memories = [memory for memory in memories if memory.type != "source"]
        for memory in memories:
            self.store.add(memory)
        return memories
```

- [ ] **Step 4: Update formation system prompt**

In `FORMATION_SYSTEM_PROMPT`, replace the Phase 2 text with:

```python
FORMATION_SYSTEM_PROMPT = """You are the memory formation model for MEMisALLuNEED.
Return only a JSON object with a memories array.
Create cleaned and compressed memories, not raw transcript copies.
Allowed memory types for chat_qa: knowledge, experience, recall.
Allowed memory states: success, failed, uncertain, contradicted, outdated.
For each chat_qa turn, emit at least one experience memory.
Every chat_qa experience memory metadata object must include source="chat_session", formation_kind="chat_qa", session_id, turn_id, recalled_memory_ids, and used_memory_ids.
If you emit a recall memory for the same turn, include the same trace metadata.
Do not emit source memories in Phase 3.
Do not include retrieval scores or recall_scores.
Do not talk to the user."""
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
pytest tests/test_formation.py::test_chat_qa_formation_does_not_write_source_memories -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add memisalluneed/formation.py tests/test_formation.py
git commit -m "Enforce Phase 3 formation output scope"
```

---

### Task 8: Add End-to-End Phase 3 CLI Trace Test

**Files:**
- Modify: `tests/test_chat_cli.py`

- [ ] **Step 1: Write focused print behavior test**

Append to `tests/test_chat_cli.py`:

```python
def test_show_memory_trace_prints_used_memories(capsys):
    item = create_memory_item(
        "Phase 3 trace memory.",
        memory_type="knowledge",
        state="success",
        confidence=1.0,
    )

    print("assistant reply")
    print(format_memory_trace([item]))

    output = capsys.readouterr().out
    assert "assistant reply" in output
    assert "Used memories:" in output
    assert f"- {item.id} knowledge success confidence=1" in output
    assert "score=" not in output
```

- [ ] **Step 2: Run test**

Run:

```bash
pytest tests/test_chat_cli.py::test_show_memory_trace_prints_used_memories -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_chat_cli.py
git commit -m "Cover Phase 3 memory trace output"
```

---

### Task 9: Update Roadmap Status

**Files:**
- Modify: `docs/roadmap.md`

- [ ] **Step 1: Inspect current roadmap**

Run:

```bash
sed -n '1,260p' docs/roadmap.md
```

Expected: roadmap lists Phase 3 as planned or not yet completed.

- [ ] **Step 2: Update Phase 3 status text**

Edit `docs/roadmap.md` so Phase 3 says it is implemented as memory-centric QA in `mem chat`, with:

```markdown
- optional `--show-memory-trace`;
- `chat_qa` formation payloads;
- one-turn rolling and exit flush formation;
- recall trace metadata through `recalled_memory_ids` and `used_memory_ids`;
- no external knowledge acquisition or source memories in Phase 3.
```

Do not mark Phase 4 or Phase 5 as implemented.

- [ ] **Step 3: Commit**

```bash
git add docs/roadmap.md
git commit -m "Document Phase 3 implementation status"
```

---

### Task 10: Full Regression and Acceptance

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run full test suite**

Run:

```bash
pytest -q
```

Expected: all tests pass.

If the environment is missing `httpx`, run in an environment with project dependencies installed:

```bash
uv sync
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Verify CLI help includes Phase 3 flag**

Run:

```bash
python -m memisalluneed.cli chat --help
```

Expected output includes:

```text
--show-memory-trace
```

- [ ] **Step 3: Verify no embedding column or vector database change was added**

Run:

```bash
rg -n "embedding|vector" memisalluneed tests docs
```

Expected: no new implementation of SQLite embedding columns, vector DB, or vector index.

- [ ] **Step 4: Verify no separate QA command was added**

Run:

```bash
python -m memisalluneed.cli --help
```

Expected: no `ask` or one-shot QA command appears.

- [ ] **Step 5: Final commit**

```bash
git add memisalluneed/cli.py memisalluneed/formation.py tests/test_chat_cli.py tests/test_formation.py docs/roadmap.md
git commit -m "Complete Phase 3 memory-centric QA"
```

---

## Self-Review Checklist

- [ ] `mem chat` remains the unified QA interface.
- [ ] No one-shot QA command is added.
- [ ] Every chat response can use recalled memories.
- [ ] `--show-memory-trace` prints ids, types, states, and confidence values.
- [ ] `used_memory_ids` equals all recalled memory ids.
- [ ] Retrieval scores are not displayed in chat trace, stored in session, or written to formation metadata.
- [ ] Recall still updates `usage_count` and `last_recalled_at`.
- [ ] Rolling formation processes one turn at a time.
- [ ] Exit flush processes remaining active turns one turn at a time.
- [ ] Formation payload uses `formation_kind = "chat_qa"`.
- [ ] Formation payload includes `session_id`, turn data, recalled memories, and `used_memory_ids`.
- [ ] `experience` memory metadata includes `session_id`, `turn_id`, `recalled_memory_ids`, and `used_memory_ids`.
- [ ] `knowledge` and `recall` memories may be emitted.
- [ ] `source` memories are not written for Phase 3.
- [ ] No immediate memory formation happens after every assistant response unless the turn rolls out of active context.
