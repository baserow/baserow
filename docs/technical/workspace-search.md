## Workspace Search

This document explains how workspace-wide search works, how results are combined, and how to add a new searchable type.

### Overview

- **Backend**: Each searchable type implements a standardized queryset which is UNION ALL'ed together and globally ordered. See `backend/src/baserow/core/search/registries.py` and `backend/src/baserow/core/search/handler.py`.
- **API**: `GET /api/search/workspace/{workspace_id}/?query=...&limit=...&offset=...` returns a flat, priority-ordered list. See `backend/src/baserow/api/search/views.py` and `backend/src/baserow/api/search/urls.py`.
- **Frontend**: `web-frontend/modules/core/store/workspaceSearch.js` calls the API via `modules/core/services/workspaceSearch.js` and powers `modules/core/components/workspace/WorkspaceSearchModal.vue`.

### Data model for combined results

All types contribute rows with the same fields (see `backend/src/baserow/core/search/constants.py`):

- **search_type**: unique type name (e.g. `table`, `view`, `row`).
- **object_id**: string id of the object.
- **sort_key**: deterministic ordering key within a type (e.g. id).
- **rank**: optional relevance score (higher is better).
- **priority**: type-level priority (lower first) to group more important types earlier.
- **title**: primary display label.
- **subtitle**: optional secondary label.
- **payload**: optional JSON for extra fields (description, timestamps, etc.).

Response items are returned as `SearchResult` dicts (see `backend/src/baserow/core/search/data_types.py`).

### Query plan and ordering

1. Each type builds a queryset filtered by permissions and `query`.
2. Each queryset is annotated to the standard fields and projected to the union schema.
3. All type querysets are combined with `UNION ALL`.
4. Global ordering is applied: `priority ASC`, `rank DESC NULLS LAST`, `sort_key ASC`, `object_id ASC`.
5. Global pagination is applied: `offset`, `limit + 1` is used to detect `has_more`.
6. Per-type postprocessing can enrich results in bulk before they are flattened back into original order.

### Backend components

- `WorkspaceSearchRegistry` (registry of types):
  - Calls each type's `get_union_values_queryset(user, workspace, context)` to build the union.
  - Applies global order and pagination.
  - Groups rows by `search_type` and calls `postprocess(rows)` per type.
- `SearchableItemType` (base class for a type):
  - Implement `get_search_queryset(user, workspace, context)` to return a base queryset filtered by permissions and query.
  - Optionally override `get_union_values_queryset(...)` to customize annotations to the standard fields.
  - Optionally override `postprocess(rows)` to batch-enrich results.
  - Optionally implement `serialize_result(...)` if using the direct (non-union) path.
- `WorkspaceSearchHandler.search_workspace(...)` orchestrates registry search and returns `{ results, has_more }`.

### API

- Endpoint: `GET /api/search/workspace/{workspace_id}/`
- Query params:
  - `query` (string, required)
  - `limit` (int, default 20)
  - `offset` (int, default 0)
- Response:
  - `results`: array of `{ type, id, title, subtitle?, description?, metadata?, created_on?, updated_on? }`
  - `has_more`: boolean

### Frontend flow

- Store: `modules/core/store/workspaceSearch.js`
  - Action `search({ workspaceId, searchTerm, limit, offset, append })` calls the API and merges results.
  - Getters provide result counts and filtering by `type`.
- Service: `modules/core/services/workspaceSearch.js` exposes `search(workspaceId, params)`.
- UI: `modules/core/components/workspace/WorkspaceSearchModal.vue` handles input, debounced requests, infinite scroll, and navigation.

### Infinite scroll and pagination

- Backend:
  - The handler requests `limit + 1` rows to detect if there are more results beyond the current page.
  - If more than `limit` rows are returned, it sets `has_more = true` and trims the list to `limit` before responding.
- Frontend:
  - Reads `has_more` from the response and stores it (e.g. `hasMoreResults`).
  - Uses the current total result count as the next `offset` when loading more.
  - Calls the same search action with `append: true` and a page-sized `limit` for subsequent loads.
  - Triggers load-more when the scroll container approaches the bottom threshold.

### Adding a new search type

1. **Create a new type class**
   - Subclass `SearchableItemType` in an appropriate module (e.g. `backend/src/baserow/<your_app>/search/types.py`).
   - Set `type` (unique string), `name` (human-readable), and optional `priority` (lower shows earlier globally).
   - Implement `get_search_queryset(user, workspace, context)`:
     - Filter to objects inside `workspace` the `user` can see.
     - Apply the `context.query` filter (ILIKE/tsvector/etc.).
     - Do not apply limit/offset here.
   - Optionally override `get_union_values_queryset(...)` to annotate the standard fields:
     - Ensure you provide: `search_type`, `object_id` (cast to text), `sort_key`, `rank` (nullable), `priority`, `title`, `subtitle`, `payload` (JSON).
   - Optionally override `postprocess(rows)` to bulk load related data and enhance titles/subtitles/payloads.

2. **Register the type**
   - Import your type and register it with `workspace_search_registry.register(MyType())` at app ready/init time (e.g. in your app `ready()` or registry module).

3. **Backend tests**
   - Add tests covering permission filtering, query matching, ordering, pagination, and `postprocess` behavior.

4. **Frontend (optional)**
   - If needed, update UI rendering to display new type-specific metadata (the store already accepts any `type`).

### Tips

- Use deterministic `sort_key` within your type to avoid jitter between pages.
- Provide a sensible `priority` so critical types appear earlier.
- If you compute a relevance `rank`, higher values should mean more relevant.
- Keep per-row work out of query execution; prefer `postprocess(rows)` for batched enrichment.


