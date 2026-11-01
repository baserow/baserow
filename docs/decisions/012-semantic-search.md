# ADR 012: Introduce semantic search

|              |                                              |
| ------------ | -------------------------------------------- |
| Status       | Proposed                                     |
| Date         | 2026-10-27                                   |
| Issue        | https://github.com/baserow/baserow/pull/6470 |
| Author       | Bram Wiepjes (@bram2w)                       |
| Contributors | Davide Silvestri (@silvestrid)               |

## Summary

Users want to find rows by the meaning of their values, not only by the words they
contain. We add semantic search as an Advanced plan feature that users enable per field.
It reuses the background lifecycle of full-text search through a shared search data
updater engine, and stores the vectors in a separate per-workspace table.

## Context

Baserow already keeps full-text search data up to date in the background: changes are
queued as pending updates, and a singleton task per table processes them, so edits
never wait for indexing.

Semantic search needs the same response to changes, but its work is different. Values
are split into chunks, the chunks are sent to an external embeddings service, and the
resulting vectors are stored with pgvector. That makes it slower, dependent on optional
infrastructure, and able to fail independently of the database.

The deciding factors were reusing the existing change tracking and recovery, keeping
edits fast, leaving full-text search unchanged, supporting instances without pgvector or
an embeddings service, and keeping the paid feature in the enterprise code.

This record covers indexing and the field setting. The search action that queries the
index (ranking, filters and permissions) is part of the semantic search action, which
builds on this.

## Options considered

| Option                                                       | Why not                                                                                                                                                       |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A separate semantic indexing pipeline                        | Duplicates queuing, throttling, singleton tasks, time budgets and periodic recovery that full-text search already has.                                        |
| One pending update table with a type column for both methods | Migrations run before the deploy, and the running version's `ON CONFLICT (field_id, row_id)` needs exactly that unique index, so the table can't be extended. |
| Store vectors in the full-text search table                  | That table has one row per cell, while a long value or file needs several chunks with their own vectors.                                                      |
| A column on the core `Field` model                           | Puts a paid feature and a core migration in the open source code.                                                                                             |
| Semantic-specific field types                                | Makes an optional search capability determine how users define their data.                                                                                    |

## Decision

### 1. A shared search data updater engine

Full-text and semantic search are search data updater types in one registry. The engine
owns what both need: queuing pending updates, processing updates of all rows of a field
before single cells, deleting only the updates that were processed, a singleton task per
type and table, a time budget per run, rescheduling and the periodic check.

Each type has its own pending update table and task. A slow or failing embeddings
service therefore never delays full-text search. Full-text search keeps its existing
table, task names and reschedule flags, so the change is safe during a rolling deploy.

### 2. An opt-in setting on existing fields

Field extensions add plugin-owned settings to ordinary fields. They're part of the field
create and update requests, responses, realtime events, undo/redo, duplication and
export/import, but never of public serializers. Exported values sit under one
`extensions` key, so an instance without the extension ignores them. Semantic search
stores the setting as an enterprise model with a one-to-one relation to the field.

### 3. Chunks and vectors in a per-workspace table

Each workspace gets a `database_semantic_search_workspace_{id}_data` table with one row
per chunk and an HNSW cosine index. It's created the first time a field of the workspace
is indexed. Vectors are only derived data, so they can always be rebuilt from the cell
values.

### 4. Only when the instance supports it

Semantic search requires pgvector and the embeddings service
(`BASEROW_EMBEDDINGS_API_URL`). Without them, or without the Advanced plan, the setting
is remembered but indexing pauses, and full-text search keeps working.

## Consequences

- **Search data is updated asynchronously.** Changes become searchable after a delay,
  and fields show a status (`indexing`, `ready`, `error`, `paused` or `unavailable`).
  Embeddings service failures are retried with a backoff.
- **The shared engine is a shared dependency.** Changes to it must keep both types
  working, and must preserve full-text behaviour and its rolling deploy compatibility.
- **Semantic search has operating costs.** Embedding calls and vector storage take
  resources. Both types run on the same export queue workers, so separate tasks don't
  reserve separate capacity.
- **The setting is a compatibility contract.** It's kept through duplication, trash,
  undo/redo, snapshots and export/import, also where the feature isn't available.
- **A different embedding model isn't detected automatically.** Unchanged cells are
  skipped by a hash that includes the embeddings service URL. Baserow ships one
  embeddings image with a pinned model, so replacing the model behind the same URL
  isn't supported.

## Revisit triggers

- We support more than one embedding model, which needs a rebuild when it changes.
