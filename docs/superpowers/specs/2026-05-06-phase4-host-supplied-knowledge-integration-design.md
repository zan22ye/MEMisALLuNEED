# Phase 4 Host-Supplied Knowledge Integration Design

## Goal

Implement Phase 4 as host-supplied knowledge integration for MEMisALLuNEED as a
memory plugin.

The host application owns external knowledge acquisition. MEMisALLuNEED receives
host-provided source references, evidence, and answer traces, then uses the
configured formation model to clean, compress, and structure those inputs into
reusable `MemoryItem` records.

## Plugin Boundary

MEMisALLuNEED must not implement:

- memory sufficiency checking;
- insufficiency reasons;
- deciding whether external knowledge is needed;
- external search;
- search model roles;
- judge model roles;
- search-judge loops;
- web browsing;
- document crawling;
- external tool calling.

The host application is responsible for:

- deciding whether memory is enough;
- deciding whether outside knowledge is needed;
- acquiring evidence and source references;
- deciding whether evidence is sufficient for its answer;
- providing structured integration inputs to MEMisALLuNEED.

MEMisALLuNEED is responsible for:

- accepting host-supplied integration inputs;
- building constrained formation payloads;
- calling the configured formation model;
- validating and filtering formation candidates;
- preserving provenance metadata;
- writing accepted memories to the `MemoryStore`.

## Architecture

Phase 4 uses API core plus CLI wrapper.

Core module:

```text
memisalluneed/integration.py
```

CLI commands:

```text
mem integrate-source
mem integrate-evidence
mem integrate-answer
```

The CLI commands should be thin wrappers around the integration API. Most
behavior should be testable through the Python API without invoking argparse.

## Formation Model Use

Phase 4 does call the formation model.

The formation model may clean, compress, and structure host-supplied material,
but it must not:

- add external facts not present in host input;
- decide whether evidence is sufficient;
- invent source references;
- remove required provenance metadata;
- store full external source text by default.

All integration APIs should send a formation payload and parse the existing
formation response shape:

```json
{"memories": [...]}
```

Formation output must be filtered by allowed memory types for each integration
kind.

## Integration Kinds

### Source Reference Integration

Purpose:

Record that the host used or discovered an external source, without storing the
source full text by default.

API:

```python
integrate_source_reference(
    store,
    formation_model,
    *,
    source_uri: str,
    source_title: str | None = None,
    retrieved_at: str | None = None,
    host_agent: str | None = None,
    metadata: dict[str, object] | None = None,
) -> list[MemoryItem]
```

Formation kind:

```text
host_source_reference
```

Allowed output memory types:

```text
source
```

Required metadata on accepted memories:

- `source = "host_supplied"`;
- `formation_kind = "host_source_reference"`;
- `source_uri`;
- `source_title`;
- `retrieved_at`;
- `host_agent`.

The implementation should preserve any host-supplied extra metadata under
normal memory metadata. It should not store full source text unless the host
explicitly provides a short source reference string as the content.

### Host Evidence Integration

Purpose:

Turn host-supplied evidence, conclusion, fact, method, or constraint into
reusable knowledge memory.

API:

```python
integrate_host_evidence(
    store,
    formation_model,
    *,
    evidence: str,
    query: str | None = None,
    source_ids: list[str] | None = None,
    host_agent: str | None = None,
    confidence: float = 1.0,
    state: str = "success",
    metadata: dict[str, object] | None = None,
) -> list[MemoryItem]
```

Formation kind:

```text
host_evidence
```

Allowed output memory types:

```text
knowledge
source
```

Primary expected memory type:

```text
knowledge
```

Required metadata on accepted memories:

- `source = "host_supplied"`;
- `formation_kind = "host_evidence"`;
- `query`;
- `source_ids`;
- `host_agent`.

If the formation model emits a `source` memory for source references supplied
by the host, the same provenance metadata should be preserved.

### Answer Trace Integration

Purpose:

Record how the host used evidence, sources, or prior memories to answer a
query. This is experience memory, not source acquisition.

API:

```python
integrate_answer_trace(
    store,
    formation_model,
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
) -> list[MemoryItem]
```

Formation kind:

```text
host_answer_trace
```

Allowed output memory types:

```text
experience
recall
```

Primary expected memory type:

```text
experience
```

Required metadata on accepted memories:

- `source = "host_supplied"`;
- `formation_kind = "host_answer_trace"`;
- `query`;
- `answer`;
- `evidence_ids`;
- `source_ids`;
- `recalled_memory_ids`;
- `host_agent`.

If the formation model emits a `recall` memory, it must preserve the same trace
metadata.

## Payload Rules

Each integration API should build a JSON-serializable payload with:

- `formation_kind`;
- host-provided input fields;
- required provenance fields;
- host-provided extra metadata.

The payload should not include tool calls, search decisions, insufficiency
reasons, or any plugin-owned acquisition state.

## Candidate Filtering

After parsing formation output, the integration layer should:

1. discard invalid memory candidates through the existing validation path;
2. discard valid candidates whose memory type is not allowed for the integration
   kind;
3. enforce required provenance metadata on accepted candidates;
4. write accepted memories to `MemoryStore`.

The integration layer may add or overwrite required provenance metadata so the
stored memories preserve host-supplied trace fields even when the formation
model omits them.

## CLI Contract

### `mem integrate-source`

Required:

- `--source-uri`

Optional:

- `--source-title`
- `--retrieved-at`
- `--host-agent`
- `--metadata` JSON object

Output:

- print written memory ids, one per line.

### `mem integrate-evidence`

Required:

- `--evidence`

Optional:

- `--query`
- `--source-id`, repeatable
- `--host-agent`
- `--confidence`
- `--state`
- `--metadata` JSON object

Output:

- print written memory ids, one per line.

### `mem integrate-answer`

Required:

- `--query`
- `--answer`

Optional:

- `--evidence-id`, repeatable
- `--source-id`, repeatable
- `--recalled-memory-id`, repeatable
- `--host-agent`
- `--confidence`
- `--state`
- `--metadata` JSON object

Output:

- print written memory ids, one per line.

## Configuration

The integration CLI should use the existing runtime config and formation model
configuration.

It should not introduce search, judge, tool, browser, crawler, or acquisition
configuration.

## Storage Policy

External source full text is not stored by default.

Host-supplied evidence may be stored as processed knowledge memory after
formation. Source references should store URI/title/provenance, not full raw
source text.

## Tests

Tests should verify:

- each API builds the expected formation payload;
- each API writes valid allowed memory candidates;
- disallowed memory types are filtered per integration kind;
- required provenance metadata is preserved or enforced;
- invalid candidates are discarded;
- CLI parsers accept the three integration commands;
- CLI commands print written memory ids;
- no search, judge, sufficiency, web, crawler, or external tool config is added;
- source full text is not required or stored by default.

## Success Criteria

- The plugin can integrate host-supplied source references into `source`
  memories.
- The plugin can integrate host-supplied evidence into `knowledge` memories.
- The plugin can integrate host-supplied answer traces into `experience`
  memories.
- Formation model output is constrained by integration kind.
- Provenance metadata is preserved.
- The CLI exposes thin wrappers for the three integration APIs.
- MEMisALLuNEED remains a memory plugin and does not perform external
  acquisition or sufficiency judgment.

