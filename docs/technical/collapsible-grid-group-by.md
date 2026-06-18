# Collapsible grid group-by

The collapsible grid group-by view renders and scrolls a large grouped table
without loading every group or every row. The design goal is to keep the flat
grid's `offset`/`limit` row-windowing behavior, but apply it to a tree of groups
so both rows and groups can scale far beyond what a fully loaded grouped row list
can handle in the browser.

This document intentionally describes the stable contract and the principles the
implementation follows. It avoids repeating function names, component names, and
store internals that are better read from the code directly. To find the current
implementation, search the codebase for the stable API concepts documented here,
especially `group-by-data`, `row_offset`, `sibling_index`, and `truncated`.

## Core Principles

### Two Independently Paged Layers

The feature is built from two data layers:

1. **Group metadata layer** - the `group-by-data` endpoint returns pages of
   groups, not rows. Each group tells the client how many rows it contains, where
   it sits among its siblings, whether it has child groups, and where its first
   descendant row appears in the full grouped row order.
2. **Row layer** - the existing grid rows endpoint still returns rows by
   `offset` and `limit`, just as it does for the flat grid.

The bridge between the layers is `row_offset`: the absolute zero-based position
of a group's first leaf row in the fully expanded grouped row order. Because the
server computes that offset, the client can fetch a leaf group's visible rows
from the ordinary rows endpoint without the rows endpoint needing to know which
groups are collapsed or expanded.

### Three Coordinate Spaces

The implementation has to keep three offset spaces separate:

- **Sibling-space** - `group-by-data` pages groups under one parent. Its
  `offset`, `limit`, and `sibling_index` are group indexes among siblings.
- **Absolute-row-space** - `row_offset` is an index into the fully expanded
  grouped row stream. The client uses it as the `offset` for the rows endpoint.
- **Visible layout-space** - the user scrolls through the currently visible
  layout, where collapsed subtrees contribute their group header but none of
  their rows.

Confusing sibling-space with absolute-row-space is the most common source of
incorrect grouped scrolling behavior.

### Sparse Tree, Sparse Rows

The client should not need the complete group tree to show a correct scrollbar
or to scroll to a deep area. Loaded group pages form a sparse tree. Unloaded
group ranges are represented as placeholders sized from the group's known
counts. Leaf rows are also sparse: rows are fetched only for visible row windows,
then cached by their absolute row offset so one row response can satisfy the
section that contains those offsets.

Rows are not treated as individual layout nodes when computing the grouped
scroll area. A leaf group can be represented as one row section with a row count,
and individual row slots are materialized only for the visible viewport. This
keeps layout size proportional to loaded group metadata, not total row count.

### Compact Collapse State

Collapse state is modeled as a mode plus exceptions:

- expand mode with no exceptions means every group is expanded;
- collapse mode with no exceptions means every group is collapsed;
- exception paths invert the current mode for specific groups.

This makes "expand all" and "collapse all" constant-size state changes,
regardless of how many groups exist. When the state is uniform, the client can
prefer depth-based group metadata loading instead of issuing one request per
visible parent.

### Viewport-Driven Fetching

Scrolling should fetch only what overlaps the visible viewport, plus whatever
buffering the grid normally needs. The client maps the viewport to:

- missing group pages by parent or by depth;
- missing absolute row ranges for visible leaf sections.

Visible parent requests can be batched into a single `group-by-data` call, and
missing row ranges can be deduplicated before calling the rows endpoint. In-flight
responses must be ignored if the grouping, collapse state, ordering, filtering,
or optimistic row counts changed after the request was sent.

### Optimistic Mutations With Server Reconciliation

Creates, updates, deletes, and moves can update the visible grouped UI before the
server responds. Local updates must keep group row counts, row locations, and
visible sections coherent. When a row moves between groups, the source and target
groups both need count updates.

The server remains authoritative when the client cannot know the final group
membership locally, for example formula-backed groups, backend-only effects,
missing group pages, or an error response that requires rollback.

### Bounded Fan-Out

Requests that include descendants must be bounded. A wide or deep group tree
must not turn one request into unbounded server work or an unbounded response.
When a descendant response is cut short by a cap, the API returns
`truncated: true` so the client can lazy-load the rest.

## API Contract

### Endpoints

Two read-only endpoints expose group metadata:

```http
GET /api/database/views/grid/{view_id}/group-by-data/
GET /api/database/views/grid/{slug}/public/group-by-data/
```

Both endpoints must apply the same filters, search, sorts, and group-by ordering
as the rows endpoint. That invariant is what makes `row_offset` line up with the
rows returned by the ordinary grid rows endpoint.

### Query Parameters

| Param                 | Meaning                                                                        |
| --------------------- | ------------------------------------------------------------------------------ |
| `offset`              | Sibling offset within the parent. This is group-space, not row-space.          |
| `limit`               | Maximum sibling groups to return, capped by the server.                        |
| `parent`              | JSON path object `{db_column: group_value}`. Omitted means top-level groups.   |
| `parents`             | JSON array of `{parent\|path, offset, limit}`. Takes precedence over `parent`. |
| `depth`               | Zero-based depth. When present, switches to depth mode.                        |
| `include_descendants` | Preload bounded first-child pages for returned groups that have children.      |
| `descendant_limit`    | Per-descendant-page group limit, capped by the server.                         |
| filters / search      | Same ad-hoc filter and search parameters accepted by the rows endpoint.        |

### Response Shape

```jsonc
{
  "pages": [
    {
      "parent": { "field_42": "active" },
      "groups": [
        {
          "path": { "field_42": "active", "field_7": "EU" },
          "depth": 1,
          "row_count": 1280,
          "children_count": 12,
          "sibling_index": 3,
          "row_offset": 51840
        }
      ],
      "offset": 0,
      "limit": 40,
      "group_count": 312
    }
  ],
  "truncated": true
}
```

`parent` is `{}` for the top level. `truncated` is present only when descendant
loading hit a cap.

The group fields are part of the frontend contract:

| Field            | Meaning                                                                 |
| ---------------- | ----------------------------------------------------------------------- |
| `path`           | Serialized group path from the root to this group.                      |
| `depth`          | Zero-based depth of this group in the active group-by hierarchy.         |
| `row_count`      | Number of leaf rows under this group after filters/search are applied.   |
| `children_count` | Number of immediate child groups. Omitted or zero at leaf depth.         |
| `sibling_index`  | This group's zero-based index among siblings under the same parent.      |
| `row_offset`     | Absolute first-row offset in the fully expanded grouped row order.       |
| `group_count`    | Total sibling group count for the page's parent.                         |

Group values in `path` and `parent` are serialized using each field type's
group-by serialization rules. The frontend must treat them as API values, not
raw database values.

### Dispatch Modes

The same endpoint supports three loading modes:

- **Single-parent mode** - `parent` asks for one page of sibling groups under one
  parent path.
- **Multi-parent mode** - `parents` asks for many parent pages in one request.
  This is useful when several visible parent groups at the same depth need their
  child pages at the same time.
- **Depth mode** - `depth=N` asks for one global page across all parents at that
  depth. This supports uniform expand/collapse states without one request per
  visible parent.

When `include_descendants` is used, the response may include bounded descendant
pages starting at offset zero. The server should thread known parent offsets into
descendant calculations so child `row_offset` values stay aligned without extra
work.

## Server-Side Responsibilities

The server owns all facts that the client cannot derive reliably:

- the group ordering after the active sorts and group-by rules;
- the row count for each group after filters and search;
- child group counts for non-leaf groups;
- sibling indexes;
- absolute row offsets in the fully expanded grouped order;
- capped descendant expansion and `truncated` signaling.

These values must be computed from the same logical row set that the rows
endpoint uses. If the rows endpoint and `group-by-data` disagree about filters,
search, sort order, or group order, row fetching by `row_offset` will place rows
in the wrong group.

## Client-Side Responsibilities

The client realizes the feature by following the API contract above:

- keep loaded group pages sparse and keyed by parent path/depth;
- render unloaded group ranges as placeholders sized from `group_count` and
  known geometry;
- map visible leaf row sections to absolute row ranges using `row_offset`;
- fetch missing rows from the ordinary rows endpoint;
- cache fetched rows by absolute offset and place them into the visible section
  that owns that offset;
- batch visible group metadata requests where possible;
- ignore stale responses after grouping, filtering, sorting, collapse state, or
  optimistic row counts change;
- update visible counts and row positions optimistically, then reconcile with the
  server response.

The public grid must use the public `group-by-data` endpoint and the public rows
endpoint, but the offset and grouping semantics are the same.

## Scalability Characteristics And Limits

The row layer scales like the flat grid: rows are fetched by true row
`offset`/`limit`, and rendering stays virtualized to the viewport.

The group layer scales by loading group metadata windows, not the complete group
tree. Query count per viewport should be proportional to visible groups and
depths, not total rows or total groups. Uniform expand/collapse states can use
depth loading to avoid request fan-out across many visible parents.

Known costs to keep in mind:

- Group metadata pages may still require the server to reason about all sibling
  groups at a level before returning one page. The page size limits the response,
  not necessarily the amount of database work needed to rank and count siblings.
- Computing child offsets is cheaper when the request already carries the
  parent's absolute row offset. Descendant loading should preserve and reuse that
  information.
- Client-side caches for loaded group pages and fetched rows can grow during a
  long scrolling session. Rendering remains virtualized, but retained metadata
  and row objects still use memory.
- Layout work should remain proportional to loaded group metadata and visible
  rows, not total rows.

## Contract Invariants

- `row_offset`, `sibling_index`, `row_count`, `children_count`, and
  `group_count` are cross-layer contract fields. Renaming or changing their
  semantics requires coordinated backend and frontend changes.
- The rows endpoint and `group-by-data` must apply the same view constraints and
  ordering.
- Geometry used for placeholders, group headers, row sections, and add-row lines
  must match the rendered UI dimensions, otherwise scroll math drifts.
- Optimistic updates must keep row counts and row placement indexes consistent
  until the next server reconciliation.
