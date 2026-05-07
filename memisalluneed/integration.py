from __future__ import annotations

from typing import Any


def build_source_reference_payload(
    *,
    source_uri: str,
    source_title: str | None = None,
    retrieved_at: str | None = None,
    host_agent: str | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "formation_kind": "host_source_reference",
        "source_uri": source_uri,
        "source_title": source_title,
        "retrieved_at": retrieved_at,
        "host_agent": host_agent,
        "metadata": dict(metadata or {}),
    }


def build_host_evidence_payload(
    *,
    evidence: str,
    query: str | None = None,
    source_ids: list[str] | None = None,
    host_agent: str | None = None,
    confidence: float = 1.0,
    state: str = "success",
    metadata: dict[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "formation_kind": "host_evidence",
        "evidence": evidence,
        "query": query,
        "source_ids": list(source_ids or []),
        "host_agent": host_agent,
        "confidence": confidence,
        "state": state,
        "metadata": dict(metadata or {}),
    }


def build_answer_trace_payload(
    *,
    query: str,
    answer: str,
    evidence_ids: list[str] | None = None,
    source_ids: list[str] | None = None,
    recalled_memory_ids: list[str] | None = None,
    host_agent: str | None = None,
    confidence: float = 1.0,
    state: str = "success",
    metadata: dict[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "formation_kind": "host_answer_trace",
        "query": query,
        "answer": answer,
        "evidence_ids": list(evidence_ids or []),
        "source_ids": list(source_ids or []),
        "recalled_memory_ids": list(recalled_memory_ids or []),
        "host_agent": host_agent,
        "confidence": confidence,
        "state": state,
        "metadata": dict(metadata or {}),
    }
