# Phase 2 Session to Memory Formation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 `mem chat`，让有界会话窗口在聊天时召回已有记忆，并在滚动或退出时通过 formation model 自动形成新的 `MemoryItem`。

**Architecture:** Phase 2 在 Phase 1 SQLite memory store 和 keyword recall 之上增加四层：本地 TOML 配置、OpenAI-compatible model adapter、有界 session window、formation pipeline。chat model 只负责回答用户，formation model 只负责清洗、压缩、结构化并写入记忆。

**Tech Stack:** Python 3.11+、`argparse`、`tomllib`、`json`、`uuid`、`httpx>=0.27`、`pytest`、SQLite。

---

## Scope

实现：

- `config.example.toml`
- `mem chat`
- `.memisalluneed/config.toml` 默认运行时配置读取
- CLI config overrides
- GPT/Kimi/Qwen OpenAI-compatible provider 配置
- active session window 持久化到 `.memisalluneed/session.json`
- `max_turns` 与近似 `max_tokens` 滚动规则
- 每轮聊天前 keyword recall
- rolling formation 与 exit flush formation
- formation JSON 校验，合法候选写入现有 SQLite memory store

不实现：

- `mem ask`
- web search 或外部知识获取
- document ingestion
- embedding、vector DB、SQLite embedding column
- graph reasoning
- conflict/outdated detection
- benchmark evaluation

---

## File Structure

新增文件：

- `config.example.toml`：版本化示例配置，不包含真实 key。
- `memisalluneed/config.py`：读取 TOML、校验字段、应用 CLI overrides、暴露 typed config。
- `memisalluneed/session.py`：`SessionTurn`、active window、近似 token 计数、`session.json` load/save/clear/roll。
- `memisalluneed/formation.py`：formation prompt、JSON parse、candidate validation、`MemoryItem` 转换与写入。
- `memisalluneed/models/__init__.py`：model package export。
- `memisalluneed/models/base.py`：provider-independent model client interface。
- `memisalluneed/models/openai_compatible.py`：OpenAI-compatible `/chat/completions` adapter。
- `tests/test_config.py`：配置加载和 overrides 测试。
- `tests/test_session.py`：session window、持久化、滚动测试。
- `tests/test_models.py`：HTTP adapter 测试，使用 fake/mock transport。
- `tests/test_formation.py`：formation parse、validation、write 测试。
- `tests/test_chat_cli.py`：`mem chat` CLI 合同测试。

修改文件：

- `pyproject.toml`：加入 `httpx>=0.27`。
- `memisalluneed/cli.py`：新增 `chat` subcommand 和 chat loop orchestration。

---

### Task 1: Config Example and Dependency

**Files:**
- Create: `config.example.toml`
- Modify: `pyproject.toml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Add dependency test**

Create `tests/test_config.py` with the first smoke test:

```python
from pathlib import Path

from memisalluneed.config import load_config


def test_load_example_config():
    config = load_config(Path("config.example.toml"))

    assert config.chat_model.provider == "openai"
    assert config.chat_model.model == "gpt-4.1"
    assert config.formation_model.provider == "openai"
    assert config.formation_model.model == "gpt-4.1-mini"
    assert config.session.max_turns == 6
    assert config.session.max_tokens == 100000
    assert config.session.recall_top_k == 5
    assert config.http.request_timeout == 60
    assert config.providers["kimi"].base_url == "https://api.moonshot.cn/v1"
    assert config.providers["qwen"].api_key_env == "QWEN_API_KEY"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: FAIL because `memisalluneed.config` and `config.example.toml` do not exist.

- [ ] **Step 3: Add `httpx` dependency**

Change `pyproject.toml`:

```toml
dependencies = [
  "httpx>=0.27",
]
```

- [ ] **Step 4: Create example config**

Write `config.example.toml`:

```toml
[chat_model]
provider = "openai"
model = "gpt-4.1"

[formation_model]
provider = "openai"
model = "gpt-4.1-mini"

[session]
max_turns = 6
max_tokens = 100000
recall_top_k = 5

[http]
request_timeout = 60

[providers.openai]
api_key_env = "OPENAI_API_KEY"
base_url = "https://api.openai.com/v1"

[providers.kimi]
api_key_env = "KIMI_API_KEY"
base_url = "https://api.moonshot.cn/v1"

[providers.qwen]
api_key_env = "QWEN_API_KEY"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

- [ ] **Step 5: Commit**

Run:

```bash
git add pyproject.toml config.example.toml tests/test_config.py
git commit -m "Add Phase 2 example config"
```

---

### Task 2: Typed Config Loader

**Files:**
- Create: `memisalluneed/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Extend config tests**

Append these tests to `tests/test_config.py`:

```python
import pytest

from memisalluneed.config import ConfigOverrides, load_config


def test_cli_overrides_replace_config_values(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[chat_model]
provider = "openai"
model = "gpt-4.1"

[formation_model]
provider = "openai"
model = "gpt-4.1-mini"

[session]
max_turns = 6
max_tokens = 100000
recall_top_k = 5

[http]
request_timeout = 60

[providers.openai]
api_key_env = "OPENAI_API_KEY"
base_url = "https://api.openai.com/v1"

[providers.qwen]
api_key_env = "QWEN_API_KEY"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(
        config_path,
        overrides=ConfigOverrides(
            chat_provider="openai",
            chat_model="gpt-4.1-mini",
            formation_provider="qwen",
            formation_model="qwen-turbo",
            max_turns=4,
            max_tokens=1200,
            recall_top_k=3,
        ),
    )

    assert config.chat_model.model == "gpt-4.1-mini"
    assert config.formation_model.provider == "qwen"
    assert config.formation_model.model == "qwen-turbo"
    assert config.session.max_turns == 4
    assert config.session.max_tokens == 1200
    assert config.session.recall_top_k == 3


def test_missing_provider_config_is_rejected(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[chat_model]
provider = "missing"
model = "model"

[formation_model]
provider = "missing"
model = "model"

[session]
max_turns = 6
max_tokens = 100000
recall_top_k = 5

[http]
request_timeout = 60
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Provider config not found: missing"):
        load_config(config_path)
```

- [ ] **Step 2: Run config tests to verify failure**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: FAIL because `ConfigOverrides` and validation are not implemented.

- [ ] **Step 3: Implement config dataclasses**

Create `memisalluneed/config.py` with these public types and functions:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

DEFAULT_CONFIG_PATH = Path(".memisalluneed") / "config.toml"


@dataclass(frozen=True)
class ModelRoleConfig:
    provider: str
    model: str


@dataclass(frozen=True)
class SessionConfig:
    max_turns: int
    max_tokens: int
    recall_top_k: int


@dataclass(frozen=True)
class HttpConfig:
    request_timeout: float


@dataclass(frozen=True)
class ProviderConfig:
    api_key_env: str
    base_url: str


@dataclass(frozen=True)
class AppConfig:
    chat_model: ModelRoleConfig
    formation_model: ModelRoleConfig
    session: SessionConfig
    http: HttpConfig
    providers: dict[str, ProviderConfig]


@dataclass(frozen=True)
class ConfigOverrides:
    chat_provider: str | None = None
    chat_model: str | None = None
    formation_provider: str | None = None
    formation_model: str | None = None
    max_turns: int | None = None
    max_tokens: int | None = None
    recall_top_k: int | None = None
```

Then implement `load_config(path, overrides=None) -> AppConfig` using `tomllib.loads(path.read_text())`, validating:

- required sections: `chat_model`, `formation_model`, `session`, `http`, `providers`;
- required model fields: `provider`, `model`;
- each selected provider exists under `[providers]`;
- provider fields: `api_key_env`, `base_url`;
- `max_turns`, `max_tokens`, `recall_top_k` are positive integers;
- `request_timeout` is positive.

- [ ] **Step 4: Run config tests**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add memisalluneed/config.py tests/test_config.py
git commit -m "Add Phase 2 config loader"
```

---

### Task 3: Model Client Interface and OpenAI-Compatible Adapter

**Files:**
- Create: `memisalluneed/models/__init__.py`
- Create: `memisalluneed/models/base.py`
- Create: `memisalluneed/models/openai_compatible.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write adapter tests**

Create `tests/test_models.py`:

```python
import httpx
import pytest

from memisalluneed.config import ProviderConfig
from memisalluneed.models.openai_compatible import OpenAICompatibleChatModel


def test_openai_compatible_model_posts_chat_completions(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["Authorization"]
        seen["json"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "assistant reply"}}]},
        )

    monkeypatch.setenv("TEST_API_KEY", "secret")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    model = OpenAICompatibleChatModel(
        provider=ProviderConfig(
            api_key_env="TEST_API_KEY",
            base_url="https://example.test/v1",
        ),
        model="test-model",
        timeout=12,
        client=client,
    )

    reply = model.complete(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
        ]
    )

    assert reply == "assistant reply"
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["authorization"] == "Bearer secret"
    assert '"model":"test-model"' in seen["json"].replace(" ", "")


def test_missing_api_key_is_clear(monkeypatch):
    monkeypatch.delenv("MISSING_API_KEY", raising=False)
    model = OpenAICompatibleChatModel(
        provider=ProviderConfig(
            api_key_env="MISSING_API_KEY",
            base_url="https://example.test/v1",
        ),
        model="test-model",
        timeout=12,
        client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))),
    )

    with pytest.raises(RuntimeError, match="Missing API key environment variable: MISSING_API_KEY"):
        model.complete([{"role": "user", "content": "hello"}])
```

- [ ] **Step 2: Run model tests to verify failure**

Run:

```bash
pytest tests/test_models.py -v
```

Expected: FAIL because model package does not exist.

- [ ] **Step 3: Implement base interface**

Create `memisalluneed/models/base.py`:

```python
from __future__ import annotations

from typing import Protocol, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class ChatModel(Protocol):
    def complete(self, messages: list[ChatMessage]) -> str:
        raise NotImplementedError
```

- [ ] **Step 4: Implement OpenAI-compatible adapter**

Create `memisalluneed/models/openai_compatible.py` with:

- constructor accepting `ProviderConfig`, `model`, `timeout`, optional `httpx.Client`;
- `complete(messages)` reading API key from `provider.api_key_env`;
- POST to `{base_url.rstrip("/")}/chat/completions`;
- JSON body with `model` and `messages`;
- `Authorization: Bearer <key>`;
- `response.raise_for_status()`;
- parse `choices[0].message.content`;
- raise `RuntimeError` for missing API key or malformed provider response.

- [ ] **Step 5: Export model types**

Create `memisalluneed/models/__init__.py`:

```python
from memisalluneed.models.base import ChatMessage, ChatModel
from memisalluneed.models.openai_compatible import OpenAICompatibleChatModel

__all__ = ["ChatMessage", "ChatModel", "OpenAICompatibleChatModel"]
```

- [ ] **Step 6: Run model tests**

Run:

```bash
pytest tests/test_models.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add memisalluneed/models tests/test_models.py
git commit -m "Add OpenAI-compatible model adapter"
```

---

### Task 4: Session Window Persistence and Rolling

**Files:**
- Create: `memisalluneed/session.py`
- Test: `tests/test_session.py`

- [ ] **Step 1: Write session tests**

Create `tests/test_session.py`:

```python
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
```

- [ ] **Step 2: Run session tests to verify failure**

Run:

```bash
pytest tests/test_session.py -v
```

Expected: FAIL because `memisalluneed.session` does not exist.

- [ ] **Step 3: Implement session module**

Create `memisalluneed/session.py` with:

- `DEFAULT_SESSION_PATH = Path(".memisalluneed") / "session.json"`;
- `SessionTurn` dataclass with fields from the spec;
- `SessionState` dataclass with `session_id`, `created_at`, `updated_at`, `turns`;
- `SessionState.new()`;
- `SessionState.load(path)` returning new state when file does not exist;
- `save(path)` creating parent dirs and writing UTF-8 JSON;
- `clear_file(path)` deleting the file if it exists;
- `add_turn(turn)`;
- `roll_excess(max_turns, max_tokens) -> list[SessionTurn]`;
- `to_dict()` and `from_dict()`;
- `approximate_tokens(text)` documented as deterministic character approximation: `(len(text) + 3) // 4`;
- active token count computed from user and assistant messages of all turns.

- [ ] **Step 4: Run session tests**

Run:

```bash
pytest tests/test_session.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add memisalluneed/session.py tests/test_session.py
git commit -m "Add bounded session window"
```

---

### Task 5: Formation Pipeline

**Files:**
- Create: `memisalluneed/formation.py`
- Test: `tests/test_formation.py`

- [ ] **Step 1: Write formation tests**

Create `tests/test_formation.py`:

```python
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
```

- [ ] **Step 2: Run formation tests to verify failure**

Run:

```bash
pytest tests/test_formation.py -v
```

Expected: FAIL because `memisalluneed.formation` does not exist.

- [ ] **Step 3: Implement formation module**

Create `memisalluneed/formation.py` with:

- `parse_memory_candidates(raw_json: str) -> list[MemoryItem]`;
- strict outer JSON checks from the spec;
- per-candidate validation using existing `create_memory_item`;
- invalid candidates skipped, invalid outer JSON returns empty list;
- `build_rolling_payload(turn, recalled_memories)`;
- `build_exit_flush_payload(turns)`;
- `build_formation_messages(payload)`;
- `FormationService.form_from_rolled_turn(turn, recalled_memories)`;
- `FormationService.form_from_exit_flush(turns)`;
- both service methods call model, parse candidates, write each valid item to `MemoryStore`, and return written items.

Formation system prompt must instruct the model to:

- return only JSON;
- produce cleaned/compressed memory, not raw transcript;
- use only supported `type` and `state` values;
- set `metadata.source = "chat_session"`;
- set `metadata.formation_kind` to `rolling` or `exit_flush`.

- [ ] **Step 4: Run formation tests**

Run:

```bash
pytest tests/test_formation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add memisalluneed/formation.py tests/test_formation.py
git commit -m "Add memory formation pipeline"
```

---

### Task 6: Chat Prompt Builder and CLI Parser Contract

**Files:**
- Modify: `memisalluneed/cli.py`
- Test: `tests/test_chat_cli.py`

- [ ] **Step 1: Write CLI parser tests**

Create `tests/test_chat_cli.py`:

```python
from memisalluneed.cli import build_parser


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
```

- [ ] **Step 2: Run CLI parser test to verify failure**

Run:

```bash
pytest tests/test_chat_cli.py -v
```

Expected: FAIL because `chat` parser does not exist.

- [ ] **Step 3: Add `chat` subparser**

Modify `build_parser()` in `memisalluneed/cli.py` to add:

- `mem chat`;
- `--config`, default `.memisalluneed/config.toml`;
- `--db`, default `.memisalluneed/memory.db`;
- `--chat-provider`;
- `--chat-model`;
- `--formation-provider`;
- `--formation-model`;
- `--max-turns`, int;
- `--max-tokens`, int;
- `--recall-top-k`, int;
- `--new-session`, action store true;
- `--clear-session`, action store true;
- `--no-resume`, action store true.

- [ ] **Step 4: Run CLI parser test**

Run:

```bash
pytest tests/test_chat_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Add mem chat CLI contract"
```

---

### Task 7: Chat Orchestration

**Files:**
- Modify: `memisalluneed/cli.py`
- Modify: `tests/test_chat_cli.py`

- [ ] **Step 1: Add orchestration tests with fake models**

Append to `tests/test_chat_cli.py`:

```python
from memisalluneed.cli import run_chat_once
from memisalluneed.config import AppConfig, HttpConfig, ModelRoleConfig, ProviderConfig, SessionConfig
from memisalluneed.schema import create_memory_item
from memisalluneed.store import MemoryStore


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
        return '{"memories":[{"type":"knowledge","content":"Rolled chat became memory.","state":"success","confidence":0.7,"metadata":{"source":"chat_session","formation_kind":"rolling"}}]}'


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
        session=SessionConfig(max_turns=0, max_tokens=100000, recall_top_k=1),
        http=HttpConfig(request_timeout=60),
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY", base_url="https://example.test/v1")},
    )

    reply = run_chat_once(
        user_message="How does Phase 2 use memory?",
        config=config,
        store=store,
        session_path=session_path,
        chat_model=chat_model,
        formation_model=formation_model,
        resume=False,
    )

    assert reply == "assistant reply using memory"
    assert "Phase 2 uses memory during chat." in chat_model.messages[-2]["content"]
    assert formation_model.calls == 1
    assert any(item.content == "Rolled chat became memory." for item in store.all())
```

- [ ] **Step 2: Run orchestration test to verify failure**

Run:

```bash
pytest tests/test_chat_cli.py::test_run_chat_once_recalls_memory_and_rolls -v
```

Expected: FAIL because `run_chat_once` does not exist.

- [ ] **Step 3: Implement prompt and one-turn orchestration**

In `memisalluneed/cli.py`, implement:

- `build_chat_messages(active_turns, recalled_results, user_message)`;
- `run_chat_once(user_message, config, store, session_path, chat_model, formation_model, resume=True)`;
- recall via existing `search_memories(store, user_message, top_k=config.session.recall_top_k)`;
- chat model messages include system prompt, recent active turns, recalled memories, current user message;
- create `SessionTurn` with user message, assistant reply, recalled memory ids;
- save active session;
- roll excess turns;
- for each rolled turn, hydrate recalled memories using `store.get(id)` and call `FormationService.form_from_rolled_turn`;
- save active session again after rolling.

Chat system prompt must say:

- this is a memory-centric assistant;
- recalled memories may be useful but incomplete;
- answer directly;
- do not claim external knowledge unless it is provided in context.

- [ ] **Step 4: Run orchestration test**

Run:

```bash
pytest tests/test_chat_cli.py::test_run_chat_once_recalls_memory_and_rolls -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Wire one-turn chat orchestration"
```

---

### Task 8: Interactive `mem chat`

**Files:**
- Modify: `memisalluneed/cli.py`
- Modify: `tests/test_chat_cli.py`

- [ ] **Step 1: Add CLI behavior tests**

Append to `tests/test_chat_cli.py`:

```python
from memisalluneed.cli import main


def test_clear_session_deletes_active_session(tmp_path):
    db_path = tmp_path / "memory.db"
    config_path = tmp_path / "config.toml"
    session_dir = tmp_path / ".memisalluneed"
    session_dir.mkdir()
    session_path = session_dir / "session.json"
    session_path.write_text('{"session_id":"s","created_at":"t","updated_at":"t","turns":[]}', encoding="utf-8")
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

    assert main(["chat", "--config", str(config_path), "--db", str(db_path), "--clear-session"]) == 0
    assert not session_path.exists()
```

- [ ] **Step 2: Run clear-session test to verify failure**

Run:

```bash
pytest tests/test_chat_cli.py::test_clear_session_deletes_active_session -v
```

Expected: FAIL until `chat` command dispatch is implemented.

- [ ] **Step 3: Implement `chat` command dispatch**

Modify `main()` in `memisalluneed/cli.py`:

- create `MemoryStore(args.db)` and `store.init()`;
- load config with overrides;
- construct chat and formation `OpenAICompatibleChatModel` from selected provider configs;
- `--clear-session` deletes `.memisalluneed/session.json` and exits 0;
- `--new-session` clears session before loop;
- `--no-resume` starts with fresh in-memory session for this run;
- interactive loop reads user input using `input("> ")`;
- `/exit`, `/quit`, and Ctrl-D trigger normal exit flush;
- each normal user message calls `run_chat_once`;
- assistant reply is printed to stdout.

- [ ] **Step 4: Implement normal exit flush**

In `memisalluneed/cli.py`, add `flush_session_on_exit(session_path, formation_model, store)`:

- load active session;
- if turns are empty, clear file and return empty list;
- call `FormationService.form_from_exit_flush(turns)`;
- clear session file only after formation returns without exception;
- return written memories.

- [ ] **Step 5: Run chat CLI tests**

Run:

```bash
pytest tests/test_chat_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Implement interactive mem chat"
```

---

### Task 9: Phase 2 Regression and Acceptance

**Files:**
- Modify: existing tests only if brittle assumptions need correction.

- [ ] **Step 1: Run full test suite**

Run:

```bash
pytest -q
```

Expected: all Phase 1 and Phase 2 tests pass.

- [ ] **Step 2: Verify CLI help includes Phase 2**

Run:

```bash
mem --help
mem chat --help
```

Expected:

- top-level help lists `chat`;
- `mem chat --help` lists all Phase 2 options from the spec.

- [ ] **Step 3: Manual mocked acceptance flow**

Because real provider calls require API keys and network access, use tests as the default acceptance path. If testing manually with real config:

```bash
mkdir -p .memisalluneed
cp config.example.toml .memisalluneed/config.toml
mem init
mem add "Phase 2 proves bounded sessions can use memory during chat."
mem chat --max-turns 1 --recall-top-k 1
```

Expected:

- each user message triggers recall;
- assistant reply is generated by configured chat model;
- when turn limit is exceeded, oldest turn is formed into memory;
- `/exit` flushes remaining active window and removes `.memisalluneed/session.json`.

- [ ] **Step 4: Confirm no forbidden SQLite schema change**

Run:

```bash
python - <<'PY'
import sqlite3
from pathlib import Path

db = Path(".memisalluneed/memory.db")
if db.exists():
    columns = [row[1] for row in sqlite3.connect(db).execute("PRAGMA table_info(memories)")]
    assert "embedding" not in columns, columns
print("no embedding column")
PY
```

Expected: prints `no embedding column`.

- [ ] **Step 5: Commit final test/doc adjustments**

Run:

```bash
git status --short
git add config.example.toml pyproject.toml memisalluneed tests
git commit -m "Complete Phase 2 session memory formation"
```

Expected: commit succeeds; `.codex`, `.memisalluneed/`, caches, and local runtime artifacts are not committed.

---

## Self-Review Checklist

- [ ] `mem chat` loads `.memisalluneed/config.toml` by default and supports `--config`.
- [ ] CLI overrides cover chat provider/model, formation provider/model, max turns, max tokens, recall top k.
- [ ] GPT, Kimi, and Qwen are represented through provider config, not provider-specific code branches.
- [ ] HTTP adapter posts to `/chat/completions` and tests use `httpx.MockTransport`.
- [ ] Chat and formation model roles remain separate.
- [ ] Every chat turn recalls existing memories before the assistant reply.
- [ ] Session persistence stores only active window, not full raw transcript.
- [ ] Rolling processes exactly one oldest turn at a time.
- [ ] Exit flush processes remaining active turns together.
- [ ] Formation validation skips invalid candidates and never writes malformed memories.
- [ ] No embedding column is added to SQLite.
- [ ] Full test suite passes with no real API keys or network access.
