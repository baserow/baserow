# Table rows full-text search

This document explains how `?search=` on a table actually works: how rows get
indexed, where the index lives, how a query is executed, and how the two search
modes relate. It's the layer that [workspace search](workspace-search.md) sits
on top of — `RowSearchType` doesn't reimplement any of this, it reads the same
index this system maintains.

## Mental model

There is a single **workspace search table** per workspace
(`database_search_workspace_{workspace_id}_data`) keyed by `(row_id, field_id)`
holding a Postgres `tsvector` in `value`. Every searchable cell in every table
in the workspace is one row in this table, with a single `GIN` index over
`value`. Indexing is **asynchronous and debounced**: code paths that change
data don't compute tsvectors inline — they queue work in
`PendingSearchValueUpdate` and a Celery task flushes the queue under a
singleton lock. Queries either hit this index (full-text mode) or fall back to
per-field `ILIKE` (compat mode).

Two things to internalise before reading the rest:

1. The tsvector data does **not** live on the user data table. The
   `database_table_{id}` tables have no `tsv_*` columns in the current world.
   They live in the per-workspace search table.
2. Full-text indexing being *enabled* and the API *defaulting* to full-text
   are two different switches. See [Search modes](#search-modes) below.

## Search modes

`SearchMode` in `backend/src/baserow/contrib/database/search/handler.py`
has two values:

- **`compat`** — per-field `ILIKE` via `FieldType.contains_query(...)`. Slow
  beyond a few thousand rows / dozens of fields. Works without any indexing
  infrastructure.
- **`full-text-with-count`** — Postgres full-text search against the workspace
  search table.

The mode is resolved per request:

```
search_mode = request_param or settings.DEFAULT_SEARCH_MODE
if mode == FT_WITH_COUNT and SearchHandler.can_use_full_text_search(table):
    pg_search(...)
else:
    compat_search(...)
```

`can_use_full_text_search` requires *both* `PG_FULLTEXT_SEARCH_ENABLED` and the
workspace search table to exist. If either is missing the request silently
falls back to `compat` — useful, but worth knowing when debugging "why is my
query slow".

The relevant env vars (all in
`backend/src/baserow/config/settings/base.py`):

| Env var | Default | Effect |
|---|---|---|
| `BASEROW_DEFAULT_SEARCH_MODE` | `"compat"` | Mode used when the request doesn't pass one. **Note: default is still `compat`** even though FT is enabled below. |
| `BASEROW_USE_PG_FULLTEXT_SEARCH` | `"true"` | Master kill-switch. Turns the workspace search table, the indexing pipeline, and the FT query path on/off. |
| `BASEROW_PG_SEARCH_CONFIG` | `"simple"` | Postgres text-search config (`tsvector` dictionary). |
| `BASEROW_PG_FULLTEXT_SEARCH_UPDATE_DATA_THROTTLE_SECONDS` | `2` | Debounce window before `update_search_data` actually runs after being scheduled. |

The default-mode-vs-enabled split is genuinely confusing. The intent is that FT
infrastructure runs everywhere so it's *available*, but callers (frontend
views, API consumers) explicitly opt in by passing `search_mode=full-text-with-count`.

## The workspace search table

Defined by `AbstractSearchValue` in
`backend/src/baserow/contrib/database/search/models.py`. The concrete model
is generated per workspace by
`SearchHandler.get_workspace_search_table_model(workspace_id)`
with the physical name
`database_search_workspace_{workspace_id}_data`.

Columns: `id`, `row_id` (int), `field_id` (int), `updated_on`, `value`
(`tsvector`). One `GIN` index named
`database_workspace_{workspace_id}_value_tsv_idx` over `value` (see
`get_search_indexes` in `models.py`). The table is created lazily on first
need via `create_workspace_search_table_if_not_exists` and dropped when the
workspace is permanently deleted. Existence is cached with
`@lru_cache(maxsize=1024)` and the cache is busted on create/delete.

## The indexing pipeline

Indexing is producer/consumer with a tiny work queue.

**Producer — `PendingSearchValueUpdate`**
(`backend/src/baserow/contrib/database/search/models.py`). Each row is a
piece of work keyed by `(field_id, row_id)` (with
`unique_together`, so duplicates coalesce). `row_id=NULL` means "reindex all
rows for this field" — used when a field definition changes, or on first
initialisation. A `deletion_workspace_id` column marks entries to be cleaned
up after a parent table/field/row is permanently deleted.

Producers are mostly in
`backend/src/baserow/contrib/database/search/receivers.py`:

- `view_loaded` — when a view is opened, fields with
  `search_data_initialized_at IS NULL` get a `(field_id, NULL)` entry and a
  schedule. This is **how indexing bootstraps lazily** — no rows are indexed
  at field creation; the index fills on first read.
- `permanently_deleted` — drops pending work for the deleted object and
  schedules cleanup of corresponding search-table rows.

Row-level producers live next to the writes (row create/update/delete) and
also call `schedule_update_search_data`. Field-level changes producers live
near the field handlers.

**Scheduler — `schedule_update_search_data`**
(`backend/src/baserow/contrib/database/search/tasks.py`). Inserts the
`PendingSearchValueUpdate` rows and queues `update_search_data` with a
`countdown` equal to the throttle setting (default 2s). Multiple calls within
the throttle window collapse to a single eventual run.

**Consumer — `update_search_data`**
(`backend/src/baserow/contrib/database/search/tasks.py`). Runs under a
singleton lock per table (so two workers can't index the same table
concurrently). Pulls pending work, batches it, and calls
`SearchHandler.process_search_data_updates(table, time_budget_seconds=...)`.
If the time budget is exhausted before the queue is empty, it reschedules
itself. This is the bit that actually computes tsvectors and writes the
search table rows.

**Safety net — `periodic_check_pending_search_data`**
(`backend/src/baserow/contrib/database/search/tasks.py`). Periodic cron.
Sweeps soft-deleted entries, drops orphans, and reschedules any table that
still has pending work but no live task — defends against worker crashes and
lost messages.

## From field value to tsvector

Each `FieldType` implements `get_search_expression(field, queryset) ->
Expression` (the base lives on the registry; see per-field implementations in
`backend/src/baserow/contrib/database/fields/field_types.py`). The expression
is a Django ORM expression that, when evaluated, returns the searchable text
representation of the cell — for example:

- Text / long text: direct cast to text.
- Single / multi-select: option name(s).
- Link row: the linked table's primary field.
- File: concatenated filenames.
- Formula: delegates to the resolved formula type.
- Number / date: cast to text.

The expression is wrapped by `LocalisedSearchVector`
(`backend/src/baserow/contrib/database/search/expressions.py`) which:

1. Runs the text through `SearchHandler.special_char_tokenizer`
   — a regex-based preprocess that splits emails, URLs,
   dates and hyphenated text so the `simple` dictionary tokenises them
   sensibly.
2. Calls the Postgres UDF `try_set_tsv(config, text)` (introduced in
   migration `0120_…`) to convert text to `tsvector`. It's a wrapper because
   the raw `to_tsvector` will error on certain inputs — `try_set_tsv` swallows
   them so a single bad cell can't block an entire indexing run.

## Executing a query

The user-facing entry point is `?search=...` on
`GET /api/database/rows/table/{id}/`
(`backend/src/baserow/contrib/database/api/rows/views.py`). It
reaches `TableModelQuerySet.search_all_fields`
(`backend/src/baserow/contrib/database/table/models.py`), which picks the
mode and dispatches:

**`pg_search` → `SearchHandler.full_text_search_in_table`**
(`backend/src/baserow/contrib/database/search/handler.py`):

1. `escape_postgres_query(input_search)` strips characters that break
   `to_tsquery` and yields a `raw`-typed query string. If sanitisation returns
   empty, the queryset is filtered to `id__in=[]` — empty result, not "no
   filter".
2. `SearchQuery(sanitized, search_type="raw", config=search_config())` is the
   matched query.
3. A CTE selects `DISTINCT row_id` from the workspace search table filtered by
   `field_id IN (...searchable fields...)` and `value = SearchQuery(...)`.
4. The CTE is `LEFT OUTER JOIN`-ed onto the row queryset; rows where the join
   matches are kept.
5. `add_exact_id_search` ORs in `Q(id=int(input_search))` when the input
   parses as a non-zero-padded integer — so `123` finds row 123 even if no
   cell contains the literal text.

**`compat_search`**: iterates `_field_objects` and ORs
together `FieldType.contains_query(...)` for each. Exact-ID OR is added
the same way.

No ranking is applied to table-level search results — order is preserved from
the underlying queryset. Workspace search *does* rank using `SearchRank`; see
its doc.

## Tokenisation parity with the frontend

The frontend doesn't run a search index, but it does highlight matched text
in cells. For that to be accurate, the frontend has to tokenise the query
string the same way Postgres did. The backend rules in
`backend/src/baserow/contrib/database/search/regexes.py` are mirrored by
`convertStringToMatchBackendTsvectorData` in
`web-frontend/modules/database/search/regexes.js`. If you change one side,
update the other or highlighting will drift from matching.

## Workspace search reads the same table

`RowSearchType`
(`backend/src/baserow/contrib/database/search_types.py`) is the
`SearchableItemType` that `WorkspaceSearchRegistry` calls for rows. It does
**not** rebuild any index — it queries the workspace search table directly
with a window function:

```
ROW_NUMBER() OVER (PARTITION BY table_id, row_id ORDER BY rank DESC, field_id ASC)
```

to dedupe and pick the best-ranking field per row, then enriches results in
`postprocess` with each table's primary-field value for display. If you find
yourself wanting to reimplement search in another `SearchableItemType` for
table data, you almost certainly shouldn't — go through this table instead.

## Operational notes

- **Backfill / rebuild**: management command `sync_table_tsvectors` (in
  `backend/src/baserow/contrib/database/management/commands/`) takes a table
  ID and re-queues every row for indexing. Use after schema changes or
  recovery from a broken state.
- **Disable temporarily**: set `BASEROW_USE_PG_FULLTEXT_SEARCH=false`.
  Existing data stays; queries fall back to `compat` until you re-enable.
- **Throttle tuning**: bump
  `BASEROW_PG_FULLTEXT_SEARCH_UPDATE_DATA_THROTTLE_SECONDS` if a workspace
  with very chatty writes is generating too many Celery tasks; reduce it if
  search results feel stale.
- **Verifying state**: `SELECT count(*) FROM database_search_workspace_<id>_data`
  confirms data is being written; `SELECT count(*) FROM
  database_pendingsearchvalueupdate` tells you the queue depth.

## Tests

`backend/tests/baserow/contrib/database/search/`:

- `backend/tests/baserow/contrib/database/search/test_search_handler.py` —
  handler methods, sanitisation, query building.
- `backend/tests/baserow/contrib/database/search/test_search_indexing.py` —
  `get_search_expression` per field type, tsvector content.
- `backend/tests/baserow/contrib/database/search/test_search_receivers.py` —
  signal-driven scheduling.
- `backend/tests/baserow/contrib/database/search/test_search_tasks.py` —
  Celery task behaviour, singleton lock, time budget, cron sweeper.
- `backend/tests/baserow/contrib/database/search/test_search_views.py` —
  end-to-end `?search=` on the row list endpoint.
- `backend/tests/baserow/contrib/database/search/test_search_compatibility.py`
  — `compat`-mode ILIKE behaviour and fallback.
- `backend/tests/baserow/contrib/database/search/test_workspace_search_handler.py`
  — workspace search table create/drop.

`backend/tests/baserow/api/test_searchable_view_mixin.py` covers the view
mixin that exposes `?search=` on viewset listings.

## Related

- [Workspace search](workspace-search.md) — how this layer is aggregated with
  other types (tables, views, etc.) into a single workspace-wide result list.
- [Field system](../patterns/field-system.md) —
  `FieldType.get_search_expression` is part of the field-type contract.
- [PostgreSQL locks](postgresql-locks.md) — the singleton lock used by
  `update_search_data`.
