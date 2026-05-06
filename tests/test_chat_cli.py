from memisalluneed.cli import ChatRunResult
from memisalluneed.cli import build_parser
from memisalluneed.cli import format_memory_trace
from memisalluneed.cli import flush_session_on_exit
from memisalluneed.cli import main
from memisalluneed.cli import run_chat_once
from memisalluneed.config import AppConfig, HttpConfig, ModelRoleConfig, ProviderConfig
from memisalluneed.config import SessionConfig
from memisalluneed.schema import create_memory_item
from memisalluneed.session import SessionState, SessionTurn
from memisalluneed.store import MemoryStore


def test_chat_parser_accepts_phase2_options():
    parser = build_parser()

    args = parser.parse_args(
        [
            "chat",
            "--config",
            "runtime.toml",
            "--db",
            "memory.db",
            "--chat-provider",
            "openai",
            "--chat-model",
            "gpt-4.1",
            "--formation-provider",
            "qwen",
            "--formation-model",
            "qwen-turbo",
            "--max-turns",
            "6",
            "--max-tokens",
            "100000",
            "--recall-top-k",
            "5",
            "--new-session",
        ]
    )

    assert args.command == "chat"
    assert args.config == "runtime.toml"
    assert args.db == "memory.db"
    assert args.chat_provider == "openai"
    assert args.formation_provider == "qwen"
    assert args.new_session is True


def test_chat_parser_accepts_show_memory_trace():
    parser = build_parser()

    args = parser.parse_args(["chat", "--show-memory-trace"])

    assert args.command == "chat"
    assert args.show_memory_trace is True


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


class FakeChatModel:
    def __init__(self):
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return "assistant reply using memory"


class FakeFormationModel:
    def __init__(self):
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        return '{"memories":[{"type":"experience","content":"Rolled chat became memory.","state":"success","confidence":0.7,"metadata":{"source":"chat_session","formation_kind":"chat_qa","session_id":"session","turn_id":"turn","recalled_memory_ids":[],"used_memory_ids":[]}}]}'


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


def test_run_chat_once_recalls_memory_and_rolls(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    store.add(create_memory_item("Phase 2 uses memory during chat."))
    session_path = tmp_path / "session.json"
    chat_model = FakeChatModel()
    formation_model = FakeFormationModel()
    config = AppConfig(
        chat_model=ModelRoleConfig(provider="openai", model="chat"),
        formation_model=ModelRoleConfig(provider="openai", model="formation"),
        session=SessionConfig(
            max_turns=0,
            max_tokens=100000,
            recall_top_k=1,
            recall_candidate_k=1,
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


def test_clear_session_deletes_active_session(tmp_path):
    db_path = tmp_path / "memory.db"
    config_path = tmp_path / "config.toml"
    session_dir = tmp_path / ".memisalluneed"
    session_dir.mkdir()
    session_path = session_dir / "session.json"
    session_path.write_text(
        '{"session_id":"s","created_at":"t","updated_at":"t","turns":[]}',
        encoding="utf-8",
    )
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
[http]
request_timeout = 60
[providers.openai]
api_key_env = "OPENAI_API_KEY"
base_url = "https://example.test/v1"
""".strip(),
        encoding="utf-8",
    )

    assert (
        main(["chat", "--config", str(config_path), "--db", str(db_path), "--clear-session"])
        == 0
    )
    assert not session_path.exists()
