import json

from memisalluneed.formation import FormationService, build_chat_qa_payload
from memisalluneed.formation import parse_memory_candidates
from memisalluneed.schema import create_memory_item
from memisalluneed.session import SessionTurn
from memisalluneed.store import MemoryStore


class FakeFormationModel:
    def __init__(self, response: str):
        self.response = response
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return self.response


def test_parse_valid_memory_candidates():
    result = parse_memory_candidates(
        """
{"memories":[{"type":"knowledge","content":"The user prefers small focused changes.","state":"success","confidence":0.9,"metadata":{"source":"chat_session","formation_kind":"rolling","turn_id":"turn-1"}}]}
""".strip()
    )

    assert len(result) == 1
    assert result[0].content == "The user prefers small focused changes."
    assert result[0].metadata["source"] == "chat_session"


def test_invalid_candidates_are_skipped():
    result = parse_memory_candidates(
        """
{"memories":[{"type":"bad","content":"","state":"success","confidence":2,"metadata":{}},{"type":"knowledge","content":"Valid memory.","state":"uncertain","confidence":0.4,"metadata":{"source":"chat_session"}}]}
""".strip()
    )

    assert len(result) == 1
    assert result[0].content == "Valid memory."


def test_chat_qa_formation_writes_valid_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    model = FakeFormationModel(
        """
{"memories":[{"type":"experience","content":"User asked about Phase 3 planning.","state":"success","confidence":0.8,"metadata":{"source":"chat_session","formation_kind":"chat_qa","session_id":"session-1","turn_id":"turn-1","recalled_memory_ids":[],"used_memory_ids":[]}}]}
""".strip()
    )
    service = FormationService(model=model, store=store)
    turn = SessionTurn(
        id="turn-1",
        user_message="make a plan",
        assistant_message="here is a plan",
        recalled_memory_ids=[],
        created_at="2026-04-26T00:00:00+00:00",
    )

    written = service.form_from_chat_qa_turn(
        session_id="session-1",
        turn=turn,
        recalled_memories=[],
    )

    assert len(written) == 1
    assert store.all()[0].content == "User asked about Phase 3 planning."
    assert model.messages[0]["role"] == "system"


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


def test_form_from_chat_qa_turn_sends_chat_qa_payload(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    recalled = create_memory_item(
        "Phase 3 turns preserve recall traces.",
        memory_type="knowledge",
    )
    store.add(recalled)
    model = FakeFormationModel(
        f"""
{{"memories":[{{"type":"experience","content":"The QA turn used recalled memory.","state":"success","confidence":0.8,"metadata":{{"source":"chat_session","formation_kind":"chat_qa","session_id":"session-1","turn_id":"turn-1","recalled_memory_ids":["{recalled.id}"],"used_memory_ids":["{recalled.id}"]}}}}]}}
""".strip()
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
