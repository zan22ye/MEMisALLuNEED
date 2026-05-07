import json

from memisalluneed.integration import build_answer_trace_payload
from memisalluneed.integration import build_host_evidence_payload
from memisalluneed.integration import build_source_reference_payload
from memisalluneed.integration import form_host_supplied_memories
from memisalluneed.integration import integrate_answer_trace
from memisalluneed.integration import integrate_host_evidence
from memisalluneed.integration import integrate_source_reference
from memisalluneed.store import MemoryStore


class FakeFormationModel:
    def __init__(self, response: str):
        self.response = response
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return self.response


def test_build_source_reference_payload():
    payload = build_source_reference_payload(
        source_uri="https://example.test/article",
        source_title="Example Article",
        retrieved_at="2026-05-06T00:00:00+00:00",
        host_agent="host-agent",
        metadata={"run_id": "run-1"},
    )

    assert payload == {
        "formation_kind": "host_source_reference",
        "source_uri": "https://example.test/article",
        "source_title": "Example Article",
        "retrieved_at": "2026-05-06T00:00:00+00:00",
        "host_agent": "host-agent",
        "metadata": {"run_id": "run-1"},
    }


def test_build_host_evidence_payload():
    payload = build_host_evidence_payload(
        evidence="The host extracted a reusable fact.",
        query="What did the host learn?",
        source_ids=["source-1"],
        host_agent="host-agent",
        confidence=0.8,
        state="success",
        metadata={"run_id": "run-1"},
    )

    assert payload == {
        "formation_kind": "host_evidence",
        "evidence": "The host extracted a reusable fact.",
        "query": "What did the host learn?",
        "source_ids": ["source-1"],
        "host_agent": "host-agent",
        "confidence": 0.8,
        "state": "success",
        "metadata": {"run_id": "run-1"},
    }


def test_build_answer_trace_payload():
    payload = build_answer_trace_payload(
        query="Why did the run fail?",
        answer="It failed because httpx was missing.",
        evidence_ids=["evidence-1"],
        source_ids=["source-1"],
        recalled_memory_ids=["memory-1"],
        host_agent="host-agent",
        confidence=0.7,
        state="uncertain",
        metadata={"run_id": "run-1"},
    )

    assert payload == {
        "formation_kind": "host_answer_trace",
        "query": "Why did the run fail?",
        "answer": "It failed because httpx was missing.",
        "evidence_ids": ["evidence-1"],
        "source_ids": ["source-1"],
        "recalled_memory_ids": ["memory-1"],
        "host_agent": "host-agent",
        "confidence": 0.7,
        "state": "uncertain",
        "metadata": {"run_id": "run-1"},
    }


def test_form_host_supplied_memories_filters_types_and_enforces_metadata(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    model = FakeFormationModel(
        """
{"memories":[{"type":"knowledge","content":"Accepted evidence memory.","state":"success","confidence":0.9,"metadata":{}},{"type":"experience","content":"Wrong type.","state":"success","confidence":0.9,"metadata":{}}]}
""".strip()
    )
    payload = build_host_evidence_payload(
        evidence="Accepted evidence memory.",
        query="What did the host learn?",
        source_ids=["source-1"],
        host_agent="host-agent",
        metadata={"run_id": "run-1"},
    )

    written = form_host_supplied_memories(
        store=store,
        formation_model=model,
        payload=payload,
        allowed_types={"knowledge", "source"},
        required_metadata={
            "source": "host_supplied",
            "formation_kind": "host_evidence",
            "query": "What did the host learn?",
            "source_ids": ["source-1"],
            "host_agent": "host-agent",
        },
    )

    sent_payload = json.loads(model.messages[1]["content"])
    assert sent_payload["formation_kind"] == "host_evidence"
    assert [memory.type for memory in written] == ["knowledge"]
    assert len(store.all()) == 1
    assert store.all()[0].metadata["source"] == "host_supplied"
    assert store.all()[0].metadata["formation_kind"] == "host_evidence"
    assert store.all()[0].metadata["query"] == "What did the host learn?"
    assert store.all()[0].metadata["source_ids"] == ["source-1"]
    assert store.all()[0].metadata["host_agent"] == "host-agent"
    assert store.all()[0].metadata["run_id"] == "run-1"


def test_integrate_source_reference_writes_source_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    model = FakeFormationModel(
        """
{"memories":[{"type":"source","content":"Source reference: Example Article https://example.test/article","state":"success","confidence":1.0,"metadata":{}},{"type":"knowledge","content":"Wrong type.","state":"success","confidence":1.0,"metadata":{}}]}
""".strip()
    )

    written = integrate_source_reference(
        store,
        model,
        source_uri="https://example.test/article",
        source_title="Example Article",
        retrieved_at="2026-05-06T00:00:00+00:00",
        host_agent="host-agent",
        metadata={"run_id": "run-1"},
    )

    assert [memory.type for memory in written] == ["source"]
    memory = store.all()[0]
    assert memory.metadata["source"] == "host_supplied"
    assert memory.metadata["formation_kind"] == "host_source_reference"
    assert memory.metadata["source_uri"] == "https://example.test/article"
    assert memory.metadata["source_title"] == "Example Article"
    assert memory.metadata["retrieved_at"] == "2026-05-06T00:00:00+00:00"
    assert memory.metadata["host_agent"] == "host-agent"
    assert memory.metadata["run_id"] == "run-1"


def test_integrate_host_evidence_writes_knowledge_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    model = FakeFormationModel(
        """
{"memories":[{"type":"knowledge","content":"The host extracted a reusable fact.","state":"success","confidence":0.8,"metadata":{}},{"type":"experience","content":"Wrong type.","state":"success","confidence":0.8,"metadata":{}}]}
""".strip()
    )

    written = integrate_host_evidence(
        store,
        model,
        evidence="The host extracted a reusable fact.",
        query="What did the host learn?",
        source_ids=["source-1"],
        host_agent="host-agent",
        confidence=0.8,
        state="success",
        metadata={"run_id": "run-1"},
    )

    assert [memory.type for memory in written] == ["knowledge"]
    memory = store.all()[0]
    assert memory.metadata["source"] == "host_supplied"
    assert memory.metadata["formation_kind"] == "host_evidence"
    assert memory.metadata["query"] == "What did the host learn?"
    assert memory.metadata["source_ids"] == ["source-1"]
    assert memory.metadata["host_agent"] == "host-agent"
    assert memory.metadata["run_id"] == "run-1"


def test_integrate_answer_trace_writes_experience_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    model = FakeFormationModel(
        """
{"memories":[{"type":"experience","content":"The host answered using supplied evidence.","state":"success","confidence":0.9,"metadata":{}},{"type":"knowledge","content":"Wrong type.","state":"success","confidence":0.9,"metadata":{}}]}
""".strip()
    )

    written = integrate_answer_trace(
        store,
        model,
        query="Why did the run fail?",
        answer="It failed because httpx was missing.",
        evidence_ids=["evidence-1"],
        source_ids=["source-1"],
        recalled_memory_ids=["memory-1"],
        host_agent="host-agent",
        confidence=0.9,
        state="success",
        metadata={"run_id": "run-1"},
    )

    assert [memory.type for memory in written] == ["experience"]
    memory = store.all()[0]
    assert memory.metadata["source"] == "host_supplied"
    assert memory.metadata["formation_kind"] == "host_answer_trace"
    assert memory.metadata["query"] == "Why did the run fail?"
    assert memory.metadata["answer"] == "It failed because httpx was missing."
    assert memory.metadata["evidence_ids"] == ["evidence-1"]
    assert memory.metadata["source_ids"] == ["source-1"]
    assert memory.metadata["recalled_memory_ids"] == ["memory-1"]
    assert memory.metadata["host_agent"] == "host-agent"
    assert memory.metadata["run_id"] == "run-1"
