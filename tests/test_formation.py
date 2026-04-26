from memisalluneed.formation import FormationService, parse_memory_candidates
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


def test_rolling_formation_writes_valid_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    model = FakeFormationModel(
        """
{"memories":[{"type":"experience","content":"User asked about Phase 2 planning.","state":"success","confidence":0.8,"metadata":{"source":"chat_session","formation_kind":"rolling","turn_id":"turn-1"}}]}
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

    written = service.form_from_rolled_turn(turn, recalled_memories=[])

    assert len(written) == 1
    assert store.all()[0].content == "User asked about Phase 2 planning."
    assert model.messages[0]["role"] == "system"
