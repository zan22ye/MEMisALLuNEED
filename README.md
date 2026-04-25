# MEMisALLuNEED

**MEMisALLuNEED** is a Memory-Centric Agent project.

The core idea is simple:

> Everything before the current moment can be treated as memory.

Instead of relying on an ever-growing context window, the system treats memory as the primary substrate of intelligence. A query is answered by recalling enough relevant memory, acquiring external knowledge only when memory is insufficient, and then writing the newly formed knowledge and experience back into memory.

## Core Thesis

For a given query, the system needs:

1. Sufficiently relevant existing memory.
2. External knowledge only when existing memory is insufficient.

After answering, the system forms new memory from the query, recalled context, answer, external knowledge, and the reasoning path used to connect them.

The system therefore grows through use.

## Memory-Centric Agent

MEMisALLuNEED is not centered on prompts, tools, or static retrieval alone. It is centered on a continuously growing memory substrate.

The agent:

- recalls relevant memories for each query;
- checks whether recalled memory is sufficient;
- acquires external knowledge when necessary;
- generates an answer from memory and knowledge;
- forms new memories from the full interaction;
- updates relations between memories over time.

In this view, memory is not only stored after answering. Memory is also formed during remembering.

## Memory Types

The system uses a unified memory item structure, while distinguishing memory by type.

### Knowledge Memory

Processed knowledge extracted from internal reasoning or external sources.

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

### Source Reference

External knowledge is not stored as full raw text by default.

Instead, the system stores references such as:

- source URL;
- title;
- access time;
- publication time when available;
- credibility or confidence notes.

The processed knowledge and its use context are stored as memory, while the original source remains referenced.

## External Knowledge Acquisition

External knowledge is not added by default for every query.

The system first recalls existing memory and performs a memory sufficiency check. External knowledge is acquired only when one or more of the following conditions hold:

- relevant memory cannot be found;
- recalled memory has low confidence;
- recalled memories conflict with each other;
- the query requires fresh or time-sensitive information;
- existing memory lacks evidence;
- existing memory only partially covers the query.

After acquisition, external knowledge is cleaned, compressed, structured, and written back as memory.

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
- relation updates.

Failures, mistakes, and uncertain answers are also written as memory, because failed experience is still useful memory. They are marked through memory state and metadata.

## Memory State and Metadata

Each memory item can include metadata such as:

- `type`: knowledge, experience, recall, or source;
- `state`: success, failed, uncertain, contradicted, or outdated;
- `confidence`;
- `created_at`;
- `source_ref`;
- `query_context`;
- `embedding`;
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

They form a graph of relationships:

- one memory can support another;
- one memory can contradict another;
- one memory can be derived from another;
- one memory can update or supersede another;
- multiple memories can be recalled together;
- memories can be linked to the answers they helped produce.

This allows the system to remember not just information, but how information interacts.

## Session Context Constraint

An active session only keeps a limited amount of raw context:

- the latest `k` dialogue turns; or
- the latest `k` tokens.

Older session content is not kept directly in the active context window. Instead, it is converted into memory through memory formation.

If older information is needed later, it must be brought back through recall.

This rule prevents the system from depending on an ever-growing prompt and forces it to rely on memory.

## Rolling Memory Write

The system uses rolling memory writes plus a lightweight per-turn check.

When the session exceeds the `k` turn or token limit:

1. the oldest content is removed from active context;
2. a smaller model cleans and compresses it;
3. new memory items are written to the memory substrate;
4. memory relations and metadata are updated.

After each query-answer turn, the system also checks whether the latest interaction produced important new memory, such as:

- new knowledge;
- user preference;
- important conclusion;
- external knowledge;
- error or failed attempt;
- recall trace;
- relation update.

## Growth Loop

The system grows through the following loop:

1. A user submits a query.
2. The system recalls relevant memories.
3. The system checks whether memory is sufficient.
4. The system acquires external knowledge if needed.
5. The system generates an answer.
6. The system forms new knowledge, experience, and recall memories.
7. The system writes new memory items into the unified memory substrate.
8. The system updates the memory graph.
9. Future queries reuse both knowledge and experience.

## Why This Matters

Traditional systems often treat context as temporary and retrieval as access to a static knowledge base.

MEMisALLuNEED treats memory as the core growing structure:

- conversations become reusable experience;
- external knowledge becomes internalized knowledge;
- recall events become future recall guidance;
- errors become marked memories instead of disappearing;
- old context is not kept in prompt, but transformed into memory.

The result is a system that can grow through interaction rather than merely respond within a context window.

## Project Status

This repository is currently in the concept and design stage.

The next step is to define the first runnable prototype:

- memory item schema;
- memory graph storage;
- recall pipeline;
- sufficiency checker;
- external knowledge acquisition interface;
- memory formation model;
- session context manager.
