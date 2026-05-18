# Workspace search

This document explains how workspace-wide search works, how results are
combined, and how to add a new searchable type.

This is the aggregation layer on top of per-type search. For row results
specifically, the `RowSearchType` is a *consumer* of the per-workspace search
table maintained by [table rows full-text search](table-rows-search.md) — it
does **not** keep a separate index. If you're trying to understand how rows
actually get indexed and matched, read that doc first; this one is about
gluing the row results together with tables, views, etc.

## Overview

- **Backend**: each searchable type implements a standard queryset. The
  handler combines them with `UNION ALL` and applies global ordering. See
  `backend/src/baserow/core/search/registries.py` and
  `backend/src/baserow/core/search/handler.py`.
- **API**:
  `GET /api/search/workspace/{workspace_id}/?query=...&limit=...&offset=...`
  returns a flat, priority-ordered list. See
  `backend/src/baserow/api/search/views.py` and
  `backend/src/baserow/api/search/urls.py`.
- **Frontend**: `web-frontend/modules/core/store/workspaceSearch.js` calls
  the API via `modules/core/services/workspaceSearch.js` and powers
  `modules/core/components/workspace/WorkspaceSearchModal.vue`.

## Data model for combined results

All types contribute rows with the same fields (see
`backend/src/baserow/core/search/constants.py`):

- **search_type**: unique type name (e.g. `table`, `view`, `row`).
- **object_id**: string id of the object.
- **sort_key**: deterministic ordering key within a type (e.g. id).
- **rank**: optional relevance score (higher is better).
- **priority**: type-level priority (lower first) to group more important
  types earlier.
- **title**: primary display label.
- **subtitle**: optional secondary label.
- **payload**: optional JSON for extra fields (description, timestamps, etc.).

Response items are returned as `SearchResult` dicts (see
`backend/src/baserow/core/search/data_types.py`). The fields above are the
union shape every type must produce. Individual `SearchableItemType`
subclasses can attach type-specific fields in `postprocess`; for example,
`RowSearchType` adds `table_id` and the primary-field value. See
[table rows full-text search](table-rows-search.md#workspace-search-reads-the-same-table).

## Query plan and ordering

1. Each type builds a queryset filtered by permissions and `query`.
2. Each queryset is annotated to the standard fields and projected to the
   union schema.
3. All type querysets are combined with `UNION ALL`.
4. Global ordering is applied: `priority ASC`, `rank DESC NULLS LAST`,
   `sort_key ASC`, `object_id ASC`.
5. Global pagination is applied: `offset`, `limit + 1` is used to detect
   `has_more`.
6. Per-type postprocessing can enrich results in bulk before they are
   flattened back into original order.

## Backend components

- `WorkspaceSearchRegistry` (registry of types):
  - Calls each type's `get_union_values_queryset(user, workspace, context)`
    to build the union.
  - Applies global order and pagination.
  - Groups rows by `search_type` and calls `postprocess(rows)` per type.
- `SearchableItemType` (base class for a type):
  - Implement `get_search_queryset(user, workspace, context)` to return a
    base queryset filtered by permissions and query.
  - Optionally override `get_union_values_queryset(...)` to customize
    annotations to the standard fields.
  - Optionally override `postprocess(rows)` to batch-enrich results.
  - Optionally implement `serialize_result(...)` if using the direct
    non-union path.
- `WorkspaceSearchHandler.search_workspace(...)` orchestrates registry
  search and returns `{ results, has_more }`.

## API

- Endpoint: `GET /api/search/workspace/{workspace_id}/`
- Query params:
  - `query` (string, required)
  - `limit` (int, default 20)
  - `offset` (int, default 0)
- Response:
  - `results`: array of `{ type, id, title, subtitle?, description?,
    metadata?, created_on?, updated_on? }` — the API serializer
    (`SearchResultSerializer` in `api/search/serializers.py`) renames the
    internal `search_type`/`object_id` to `type`/`id` and unpacks
    `payload` into the top-level optional fields.
  - `has_more`: boolean

## Frontend flow

- Store: `modules/core/store/workspaceSearch.js`
  - Action `search({ workspaceId, searchTerm, limit, offset, append })`
    calls the API and merges results.
  - Getters provide result counts and filtering by `type`.
- Service: `modules/core/services/workspaceSearch.js` exposes
  `search(workspaceId, params)`.
- UI: `modules/core/components/workspace/WorkspaceSearchModal.vue` handles
  input, debounced requests, infinite scroll, and navigation.

## Infinite scroll and pagination

- Backend:
  - The handler requests `limit + 1` rows to detect whether there are more
    results beyond the current page.
  - If more than `limit` rows are returned, it sets `has_more = true` and
    trims the list to `limit` before responding.
- Frontend:
  - Reads `has_more` from the response and stores it (e.g. `hasMoreResults`).
  - Uses the current total result count as the next `offset` when loading more.
  - Calls the same search action with `append: true` and a page-sized
    `limit` for subsequent loads.
  - Triggers load-more when the scroll container approaches the bottom threshold.

## Adding a new search type

1. **Create a new type class**
   - Subclass `SearchableItemType` in an appropriate module, for example
     `backend/src/baserow/<your_app>/search/types.py`.
   - Set `type` (unique string), `name` (human-readable), and optional
     `priority` (lower shows earlier globally).
   - Implement `get_search_queryset(user, workspace, context)`:
     - Filter to objects inside `workspace` the `user` can see.
     - Apply the `context.query` filter (ILIKE/tsvector/etc.).
     - Do not apply limit/offset here.
   - Optionally override `get_union_values_queryset(...)` to annotate the
     standard fields.
   - Ensure you provide: `search_type`, `object_id` (cast to text),
     `sort_key`, `rank` (nullable), `priority`, `title`, `subtitle`, and
     `payload` (JSON).
   - Optionally override `postprocess(rows)` to bulk load related data and
     enhance titles, subtitles, or payloads.

2. **Register the type**
   - Import your type and register it with
     `workspace_search_registry.register(MyType())` at app ready/init time
     (for example, in your app `ready()` or registry module).

3. **Backend tests**
   - Add tests covering permission filtering, query matching, ordering,
     pagination, and `postprocess` behaviour.

4. **Frontend (optional)**
   - If needed, update UI rendering to display new type-specific metadata (the store already accepts any `type`).

## Tips

- Use deterministic `sort_key` within your type to avoid jitter between pages.
- Provide a sensible `priority` so critical types appear earlier.
- If you compute a relevance `rank`, higher values should mean more relevant.
- Keep per-row work out of query execution; prefer `postprocess(rows)` for batched enrichment.
