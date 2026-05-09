# MEMisALLuNEED

**MEMisALLuNEED** is a Memory-Centric Agent project.

The core idea is simple:

> Everything before the current moment can be treated as memory.

Instead of relying on an ever-growing context window, the system treats memory as the primary substrate of intelligence. A query is answered by recalling relevant memory, using host-supplied external knowledge when the host application provides it, and then writing newly formed knowledge and experience back into memory.

## Core Thesis

For a given query, the system needs:

1. Sufficiently relevant existing memory.
2. Host-supplied external knowledge when the host application decides memory alone is insufficient.

After answering, the system forms new memory from the query, recalled context, answer, host-supplied evidence when present, and the reasoning path used to connect them.

The system therefore grows through use.

## Implementation Boundary

MEMisALLuNEED is the memory core. It stores, recalls, resolves, and forms memory.

It does not itself search the web, crawl documents, call external tools, judge whether external evidence is sufficient, or decide that outside knowledge is needed. Those responsibilities belong to a host application. MEMisALLuNEED can integrate external knowledge after the host supplies sources, evidence, and answer traces.

## Memory-Centric Agent

MEMisALLuNEED is not centered on prompts, tools, or static retrieval alone. It is centered on a continuously growing memory substrate.

The agent:

- recalls relevant memories for each query;
- uses host-supplied external knowledge when provided;
- generates an answer from memory and knowledge;
- forms new memories from the full interaction;
- is designed to support memory relations in future phases.

In this view, memory is not only stored after answering. Memory is also formed during remembering.

## Memory Types

The system uses a unified memory item structure, while distinguishing memory by type.

### Knowledge Memory

Processed knowledge extracted from internal reasoning or host-supplied external sources.

Examples:

- facts;
- concepts;
- summaries;
- entity relationships;
- methods;
- conclusions.

### Experience Memory

Memory about how knowledge was used in a specific query-answer process.

It records:

- what the query was asking;
- why certain knowledge was relevant;
- how the knowledge supported the answer;
- whether the answer was successful, failed, uncertain, or incomplete.

### Recall Memory

A compact trace of a recall event.

It records:

- which memories were recalled;
- why they were relevant;
- how they were combined;
- how they contributed to the final answer.

### Host-Supplied Source Reference

Host-supplied external knowledge is not stored as full raw text by default.

In Phase 4, the planned source integration stores references such as:

- source URL;
- title;
- access time;
- publication time when available;
- credibility or confidence notes.

The processed knowledge and its use context are stored as memory, while the original source remains referenced. Current `mem chat` does not write `source` memories; host-supplied source reference integration is a planned Phase 4 capability.

## Host-Supplied External Knowledge

External knowledge is not added by default for every query.

A host application may decide that existing memory is insufficient and provide external evidence or source references when one or more of the following conditions hold:

- relevant memory cannot be found;
- recalled memory has low confidence;
- recalled memories conflict with each other;
- the query requires fresh or time-sensitive information;
- existing memory lacks evidence;
- existing memory only partially covers the query.

After the host supplies that material, MEMisALLuNEED can clean, compress, structure, and write it back as memory. MEMisALLuNEED does not perform the external acquisition itself.

## Memory Formation

Memory is automatically written, but not as raw conversation logs.

Before writing, a smaller model cleans and structures memory candidates. The goal is to preserve complete meaning while making the memory as concise as possible.

Memory formation includes:

- deduplication;
- compression;
- noise removal;
- knowledge extraction;
- experience extraction;
- recall trace generation;
- metadata assignment;
- planned relation metadata for future graph support.

Failures, mistakes, and uncertain answers are also written as memory, because failed experience is still useful memory. They are marked through memory state and metadata.

## Memory State and Metadata

Each memory item can include metadata such as:

- `type`: knowledge, experience, recall, or source;
- `state`: success, failed, uncertain, contradicted, or outdated;
- `confidence`;
- `created_at`;
- `source_ref`;
- `query_context`;
- `vector_index_ref` or `semantic_index_ref`;
- `usage_count`;
- `last_recalled_at`;
- `derived_from`;
- `supports`;
- `contradicts`;
- `updates`;
- `supersedes`;
- `recalled_with`;
- `used_in`.

The system does not separate memory into short-term and long-term memory. All formed memories live in one memory substrate. Their future usefulness is determined at recall time through relevance, confidence, freshness, usage, and relations.

## Memory Graph

Memory items are not isolated text chunks.

The project is designed so future phases can represent a graph of relationships:

- one memory can support another;
- one memory can contradict another;
- one memory can be derived from another;
- one memory can update or supersede another;
- multiple memories can be recalled together;
- memories can be linked to the answers they helped produce.

This is a planned Phase 5 capability. Current `mem chat` does not perform graph reasoning or automatic relation updates.

## Session Context Constraint

An active session only keeps a limited amount of raw context:

- the latest `k` dialogue turns; or
- the latest `k` tokens.

Older session content is not kept directly in the active context window. Instead, it is converted into memory through memory formation.

If older information is needed later, it must be brought back through recall.

This rule prevents the system from depending on an ever-growing prompt and forces it to rely on memory.

## Rolling And Flush Memory Formation

The current chat flow uses rolling memory formation plus exit flush formation.

When the session exceeds the `k` turn or token limit:

1. the oldest content is removed from active context;
2. a smaller model cleans and compresses it;
3. new memory items are written to the memory substrate;
4. metadata is attached to preserve the chat formation trace.

When the user exits chat, remaining active turns are flushed into memory. Current `mem chat` does not immediately form memory after every assistant response.

## Growth Loop

The system grows through the following loop:

1. A user submits a query.
2. The system recalls relevant memories.
3. The system resolves the recalled candidates into bounded chat context.
4. The system generates an answer from active session context and recalled memory.
5. The host application may supply external sources, evidence, or answer traces.
6. The system forms new knowledge, experience, and recall memories during rolling or exit flush formation.
7. The system writes new memory items into the unified memory substrate.
8. Future queries reuse both knowledge and experience.

## Why This Matters

Traditional systems often treat context as temporary and retrieval as access to a static knowledge base.

MEMisALLuNEED treats memory as the core growing structure:

- conversations become reusable experience;
- host-supplied external knowledge can become internalized knowledge;
- recall events become future recall guidance;
- errors become marked memories instead of disappearing;
- old context is not kept in prompt, but transformed into memory.

The result is a system that can grow through interaction rather than merely respond within a context window.

## CLI Quickstart

The current runnable interface is the `mem` CLI.

```bash
mem init
mem add "Everything before the current moment can be treated as memory."
mem add "Host-supplied external knowledge is integrated only after the host provides it."
mem list
mem search "when should external knowledge be used"
mem export
```

Runtime data is stored in `.memisalluneed/memory.db`, which is ignored by git.

Memory-centric chat is available through:

```bash
mem chat
```

The chat flow recalls relevant memories, keeps the active session bounded,
rolls older turns into memory, and can show the recalled memory trace:

```bash
mem chat --show-memory-trace
```

DeepSeek can be used through the existing OpenAI-compatible provider layer.
Set `DEEPSEEK_API_KEY`, then override the provider and model:

```bash
mem chat --chat-provider deepseek --chat-model deepseek-chat
```

SiliconFlow can also be used through the same OpenAI-compatible provider
layer. Set `SILICONFLOW_API_KEY`, then choose a SiliconFlow model:

```bash
mem chat --chat-provider siliconflow --chat-model Pro/zai-org/GLM-4.7
```

## Project Status

This repository has progressed beyond the initial concept stage.

Implemented:

- Phase 1: CLI memory substrate with SQLite storage and JSONL export.
- Phase 2: session-to-memory formation through `mem chat`.
- Phase 3: memory-centric QA behavior inside `mem chat`.
- Phase 3.5: deterministic timestamp-aware memory resolution for chat context.

Current CLI commands:

- `mem init`
- `mem add`
- `mem list`
- `mem show`
- `mem search`
- `mem export`
- `mem chat`

Phase 4 is not implemented yet. The current Phase 4 direction is
host-supplied knowledge integration: the host application acquires sources and
evidence, while MEMisALLuNEED accepts that host-provided material and forms
structured memories from it. The planned interfaces are:

- `mem integrate-source`
- `mem integrate-evidence`
- `mem integrate-answer`

These Phase 4 commands are design targets, not currently available CLI
commands.
