from memisalluneed.session import SessionState, SessionTurn, approximate_tokens


def test_approximate_tokens_is_deterministic():
    assert approximate_tokens("abcd") == 1
    assert approximate_tokens("abcde") == 2
    assert approximate_tokens("") == 0


def test_session_save_load_and_clear(tmp_path):
    path = tmp_path / "session.json"
    state = SessionState.new()
    state.turns.append(
        SessionTurn(
            id="turn-1",
            user_message="hello",
            assistant_message="reply",
            recalled_memory_ids=["mem-1"],
            created_at="2026-04-26T00:00:00+00:00",
        )
    )

    state.save(path)
    loaded = SessionState.load(path)

    assert loaded.session_id == state.session_id
    assert loaded.turns[0].id == "turn-1"
    assert loaded.turns[0].recalled_memory_ids == ["mem-1"]

    loaded.clear_file(path)
    assert not path.exists()


def test_roll_limits_by_turn_count():
    state = SessionState.new()
    for index in range(3):
        state.turns.append(
            SessionTurn(
                id=f"turn-{index}",
                user_message=f"user {index}",
                assistant_message=f"assistant {index}",
                recalled_memory_ids=[],
                created_at="2026-04-26T00:00:00+00:00",
            )
        )

    rolled = state.roll_excess(max_turns=2, max_tokens=100000)

    assert [turn.id for turn in rolled] == ["turn-0"]
    assert [turn.id for turn in state.turns] == ["turn-1", "turn-2"]
