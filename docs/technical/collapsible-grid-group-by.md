# Collapsible grid group-by

The collapsible grid group-by view renders and scrolls a large grouped table
without loading every group or every row. The design goal is to keep the flat
grid's row-windowing behavior — fetch rows by absolute offset and limit — but
apply it to a tree of groups, so both rows and groups can scale far beyond what
a fully loaded grouped row list can handle in the browser.

This document describes the stable approach and the tradeoffs behind it. It
deliberately avoids endpoint shapes, parameter lists, field-by-field schemas,
function names, and store internals: those drift and are better read from the
code. To find the current implementation, search the codebase for the durable
concepts named here, especially `group-by-data`, `row_offset`, `sibling_index`,
and `truncated`.

## Core Principles

### Two Independently Paged Layers

The feature is built from two data layers:

1. **Group metadata layer** - a dedicated endpoint returns pages of groups, not
   rows. Each group tells the client how many rows it contains, where it sits
   among its siblings, whether it has child groups, and where its first
   descendant row appears in the full grouped row order.
2. **Row layer** - the existing grid rows endpoint still returns rows by offset
   and limit, just as it does for the flat grid.

The bridge between the layers is `row_offset`: the absolute zero-based position
of a group's first leaf row in the fully expanded grouped row order. Because the
server computes that offset, the client can fetch a leaf group's visible rows
from the ordinary rows endpoint without the rows endpoint needing to know which
groups are collapsed or expanded.

### Three Coordinate Spaces

The implementation has to keep three offset spaces separate:

- **Sibling-space** - the group metadata layer pages groups under one parent.
  Its offsets and the `sibling_index` are group indexes among siblings.
- **Absolute-row-space** - `row_offset` is an index into the fully expanded
  grouped row stream. The client uses it as the offset for the rows endpoint.
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
regardless of how many groups exist. Collapse-all only ever shows the top-level
headers, so it loads its single visible depth with depth-based group metadata.
Expand-all and mixed states load per parent, descending each visible parent's
subtree to its leaves so one request returns everything the viewport needs
instead of one request per depth.

### Viewport-Driven Fetching

Scrolling should fetch only what overlaps the visible viewport, plus whatever
buffering the grid normally needs. The client maps the viewport to:

- missing group pages by parent or by depth;
- missing absolute row ranges for visible leaf sections.

Visible parent requests can be batched into a single group metadata call, and
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

Once the server resolves a group change through a read-only or formula-backed
group field, the row moves to that group immediately, even while selected. The
selected-row move-warning placeholder is only useful for directly writable group
fields whose in-progress edit must remain visible until deselection.

### Row Ordering Inside Groups

Grouped rows keep the table's manual row order as the final ordering key inside
each leaf group. When no explicit view sort is active, a visible row insertion
slot can therefore move a row before another row in the same leaf group or to
that group's end.

A move to another leaf group first replaces the row values represented by the
complete destination group path and then updates its order. These are separate
API requests with the same action group, so one undo or redo applies both changes.
If the order request fails after the value update succeeds, the row remains in the
destination group at its previous order. Cross-group moves are available only when
every active group-by field is writable; if any grouped field is read-only, rows
can only be reordered inside their current leaf group. Collapsed groups and
unloaded row placeholders are not drop targets because they do not expose an
unambiguous visible insertion slot.

### Bounded Fan-Out

Requests that include descendants must be bounded. A wide or deep group tree
must not turn one request into unbounded server work or an unbounded response.
When a descendant response is cut short by a cap, the API signals truncation (the
`truncated` flag) so the client can lazy-load the rest.

## Group Metadata API

A read-only group metadata endpoint, with a matching public-view variant,
returns group metadata in pages: which groups exist under a parent, how many
rows and child groups each has, where each group sits among its siblings, and the
absolute row offset of its first leaf row. It can also bundle the footer totals
and preload a bounded slice of descendants in the same round trip. The exact
parameters, response shape, and field names live in the serializer and view code.

The endpoint supports three request shapes, chosen by what the viewport needs:

- a single parent's page of child groups;
- several parents' pages in one round trip, for when multiple visible parents at
  the same depth all need their children at once;
- a whole-depth page across all parents, which serves uniform expand/collapse
  states without one request per visible parent.

Two invariants make this work:

- The group metadata query and the rows query must apply identical filters,
  search, sorts, and group ordering. If they disagree, fetching rows by a group's
  `row_offset` places them in the wrong group.
- Descendant preloading must be bounded; when a cap cuts a response short, the
  API signals truncation so the client can lazy-load the remainder.

Group values in group paths are serialized using each field type's group-by
serialization rules. The frontend must treat them as API values, not raw database
values.

## Server-Side Responsibilities

The server owns all facts that the client cannot derive reliably:

- the group ordering after the active sorts and group-by rules;
- the row count for each group after filters and search;
- child group counts for non-leaf groups;
- sibling indexes;
- absolute row offsets in the fully expanded grouped order;
- capped descendant expansion and truncation signaling.

These values must be computed from the same logical row set that the rows
endpoint uses. If the rows endpoint and the group metadata layer disagree about
filters, search, sort order, or group order, row fetching by `row_offset` will
place rows in the wrong group.

## Client-Side Responsibilities

The client realizes the feature by following the API contract above:

- keep loaded group pages sparse and keyed by parent path/depth;
- render unloaded group ranges as placeholders sized from known sibling counts
  and geometry;
- map visible leaf row sections to absolute row ranges using `row_offset`;
- fetch missing rows from the ordinary rows endpoint; on the initial expand-all
  load the first rows page (offset 0) is fetched in parallel with the group
  skeleton, since expand-all renders rows in sorted order independent of the tree;
- cache fetched rows by absolute offset and place them into the visible section
  that owns that offset;
- batch visible group metadata requests where possible;
- ignore stale responses after grouping, filtering, sorting, collapse state, or
  optimistic row counts change;
- update visible counts and row positions optimistically, then reconcile with the
  server response.

The public grid must use the public group metadata endpoint and the public rows
endpoint, but the offset and grouping semantics are the same.

## Scalability Characteristics And Limits

The row layer scales like the flat grid: rows are fetched by true row
offset/limit, and rendering stays virtualized to the viewport.

The group layer scales by loading group metadata windows, not the complete group
tree. Query count per viewport should be proportional to visible groups and
depths, not total rows or total groups. Collapse-all uses depth loading for its
single visible level. Expand-all loads each visible parent's subtree to the
leaves in one request (budgeted by leaf rows), so the initial viewport is a
single round-trip instead of one request per depth.

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

- A small set of cross-layer fields — the absolute row offset, sibling index, row
  count, child count, and total sibling count — form a contract between backend
  and frontend. Renaming them or changing their semantics requires coordinated
  backend and frontend changes.
- The rows endpoint and the group metadata layer must apply the same view
  constraints and ordering.
- Geometry used for placeholders, group headers, row sections, and add-row lines
  must match the rendered UI dimensions, otherwise scroll math drifts.
- Optimistic updates must keep row counts and row placement indexes consistent
  until the next server reconciliation.
- Cross-group row moves must update the complete destination group path before
  changing order. A failed order request does not roll back a successful group
  value update.

## Group Aggregations

When a column has a footer "Summarize" aggregation, each group header shows that
aggregation computed over the group's rows, at every depth. The values travel
inside the group metadata response, and the footer total can be bundled into the
same request, so grouped mode never calls the standalone aggregations endpoint.

Updates are consolidated and backend-authoritative. A single group metadata
request refreshes both the loaded group window and the footer totals, and every
edit path and the realtime echo funnel through the same group-aware refresh. Row
edits refresh silently; a spinner is reserved for changing a column's aggregation
function. Sorting needs no refresh because these aggregations are
order-independent.
