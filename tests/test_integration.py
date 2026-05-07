from memisalluneed.integration import build_answer_trace_payload
from memisalluneed.integration import build_host_evidence_payload
from memisalluneed.integration import build_source_reference_payload


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
