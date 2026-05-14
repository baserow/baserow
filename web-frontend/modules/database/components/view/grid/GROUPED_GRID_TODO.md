# Grouped Grid Parity — Status & TODO

Status of the per-section grouped grid (`page/view/gridGrouped` store +
`GridGrouped` component) compared to the legacy flat grid
(`page/view/grid` store + `GridView`/`GridViewSection`).

Sharing classification:
- **Shared** — same module/helper used by both grids.
- **Mirrored** — separate code per grid but routed from the same
  callsite (e.g., realtime dispatchers fire to both stores).
- **Duplicated** — separate code per grid, intentional or pending
  extraction.

---

## ✅ Done

### Store / pure logic

| Feature | Where | Sharing |
|---|---|---|
| Row sort function | `utils/view.js::getRowSortFunction` | **Shared** |
| Search match calc | `utils/view.js::calculateSingleRowSearchMatches` | **Shared** |
| Row metadata mutate | `utils/row.js::updateRowMetadataType` | **Shared** |
| Prep new/old/request values (single cell) | `utils/row.js::prepareNewOldAndUpdateRequestValues` | **Shared** |
| Prep multi-field update (paste rectangle) | `utils/row.js::prepareRowMultiFieldUpdate` | **Shared** (added for grouped, reusable by flat) |
| Row lifecycle helpers (create/delete/reapply match) | `utils/rowLifecycle.js` | **Shared** via adapter callbacks |
| Per-section bucket model | `store/view/gridGrouped.js` | grouped-only |
| Optimistic edit + section move | `store/view/gridGrouped.js::optimisticEditRow` | grouped-only |
| Order-change in-memory resort (no refetch) | `RESORT_SECTION_BUCKET` + handleRealtimeRowUpdated | grouped-only |

### Row interactions

| Feature | Sharing | Notes |
|---|---|---|
| Inline cell edit (text/number/date/select/…) | **Shared** (`GridViewCell`) | Both grids mount the same cell component. |
| Cell selection (single) | **Mirrored** | Grouped has its own `selectedCell` state; flat uses different state shape. |
| Multi-cell area selection | **Shared store state** | Grouped writes to flat's `view/grid` multi-select indices (head/tail/start). |
| Checkbox row selection | **Shared store state** | Grouped reads `view/grid/getCheckboxSelectedRowsIds`. |
| Copy / Cmd-C | **Shared mixin** (`copyPasteHelper`) | |
| Multi-cell paste (rectangle) | **Mirrored** | Grouped sends ONE `batchUpdate` for N rows × M fields via `batchUpdateRowValues`. |
| Row drag handle + within-section reorder | **Duplicated** | `GridGroupedRowDragging` mirrors `GridViewRowDragging` — different coordinate system (absolute-positioned canvas vs row buffer). |
| Cross-section drag (group-by patch) | grouped-only | `moveRowToSection` → `batchUpdateRowValues`. |
| Field column reorder via header drag | **Shared** (`GridViewFieldDragging`) | Same overlay component, wired from grouped's `GridViewHead`. |
| Row context menu (right-click single row) | **Shared component** (`GridRowContextItems`) | |
| Multi-row context menu (right-click on selection) | **Shared component** (`GridMultiRowContextItems`) | |
| Row expand button → open row modal | **Mirrored** | Grouped row uses the same `getRowExpandButtonComponent`; modal is owned by flat-grid parent. |
| Row coloring (decorator: first_cell + wrapper) | **Mirrored** | Grouped inlines the `decorationsByPlace` computation (`viewDecoration` mixin's prop coupling made the mixin awkward). |
| Outside-click clears multi-select | grouped-only (handler mirrors flat) | |

### View-config / realtime

| Feature | Sharing | Notes |
|---|---|---|
| Filters change → refresh | grouped-only watcher in `GridGrouped.vue` | Watches `view.filters` deep, calls `refreshForViewConfigChange`. |
| Sortings change → refresh | grouped-only watcher | |
| Group-by config change → structural reset | grouped-only | `SET_GROUP_BY_FIELDS` mutation + tree reset. |
| Row height switching | **Mirrored** | Same constant (`GRID_VIEW_SIZE_TO_ROW_HEIGHT_MAPPING`); grouped stores its own `state.rowHeight`. |
| Collapse all / Expand all | grouped-only | Added action `setCollapsedAll` + UI buttons in `ViewGroupByContext.vue`. |
| Search highlight | grouped-only watcher | Iterates section buckets, applies match flags via shared helper. |
| Search hide-mode | grouped-only | `setActiveSearch` action passes search to BE in `fetchTree` / `fetchSectionRows` when hide-mode + non-empty. |
| Aggregations footer | **Shared component** (`GridViewFieldFooter`) | |
| Total row count | grouped-only getter | Sums leaf nodes' `rowCount` in tree. |

### Realtime events

| Event | Routing | Notes |
|---|---|---|
| `rowCreated` | **Mirrored** (`viewTypes.js`) | Dispatched to both flat and grouped stores when V2 module mounted. |
| `rowUpdated` | **Mirrored** | Grouped re-runs match flags + in-memory resort on order change. |
| `rowDeleted` | **Mirrored** | |
| `rowMetadataUpdated` | **Mirrored** | Both `view/grid/updateRowMetadata` and grouped variant. |
| `afterFieldCreated/Updated/Deleted` | **Mirrored** | Grouped path calls `refreshForViewConfigChange` when relevant. |
| `fieldOptionsUpdated` | flat-only dispatch | Grouped reads via shared `fieldOptions` prop from `GridView`. |
| `AIValuesGenerationError` | flat-only dispatch | ❌ Not routed to grouped — see TODO. |

---

## 🟨 Verified working but not formally tested

- Field column resize affecting grouped canvas width recompute.
- Right-click field menu actions (rename, delete, change type).
- Cell editor dropdown positioning in tall row heights (`large` row-height-size).
- Field column reorder via header drag (wired this session — dragging
  container activates on mousedown; reorder fires through shared
  flat-store options dispatch).

E2E + Vitest coverage:
- ✅ Store unit tests: 67 passing (`test/unit/database/store/view/gridGrouped.spec.js`).
- ✅ E2E specs: `grouped_grid_row_drag`, `grouped_grid_search`, `grouped_grid_collapse_all` — all green in `just e2e run`.

---

## ❌ Still missing / not done

### User-facing gaps

| Item | Priority | Notes |
|---|---|---|
| **Bulk row add per section ("+5/+10/+50")** | medium | Flat has `GridViewRowsAddContext`; grouped only has single-row trailer. Needs a `createNewRowsInGroup` action + caret-menu next to each section's trailer. |
| **Multi-row drag** | low | Drag a group of checkbox-selected rows together. Grouped only drags one row at a time. |
| **Public/shared view rendering** | high | `gridGrouped` not registered under `publicBuilder/` or `template/` namespaces. A publicly-shared grouped view will not render. Needs module registration + `publicAuthToken` threaded through every fetch + read-only checks. |
| **Row-modal prev/next navigation** | medium | Modal opens fine, but prev/next iterates flat's `allRows` which is empty when grouped is active. Needs grouped to expose a linear row list to the modal. |
| **AI generation error realtime** | low | `viewTypes.js::AIValuesGenerationError` only dispatches to flat. |
| **Frozen columns** | low | Flat splits left/right panes for `frozen_column_count > 1`. Grouped uses single canvas; ignores the setting. |

### Robustness / polish

| Item | Notes |
|---|---|
| Group-by reorder UX flash | Optimistic structural reset flashes empty grid briefly. Could pre-compute new layout to avoid the flash. |
| Wrapper-decoration mixin extraction | Decoration computation is inlined in `GridGrouped.vue` to avoid the `viewDecoration` mixin's `fields` prop coupling. Could unify by relaxing the mixin or wrapping it. |
| Row-coloring CSS edge cases | Wrapper decoration wraps inner row, which inherits `border-bottom`. Some color decorators may need extra padding adjustments. |
| Sparse-bucket order resort fallback | Realtime order change falls back to refetch when bucket is non-contiguous. Could be improved with a proper sparse re-sort if it becomes a performance issue. |
| Group-by field swap visual continuity | Brief blank state during structural reset. |

---

## 🔧 Pending shared-code extraction (post-parity)

Per the original PR1 plan ("extract every feature into pure or
reusable functions"), the following are candidates for consolidation
once both grids are stable:

1. **Row drag component** — share a base with two coordinate adapters
   (absolute-canvas-y vs flat-buffer-y).
2. **Row template** — `GridViewRow` vs `GridGroupedRow` differ only in
   the positioning shell and section-binding props. A shared base
   slot pattern could fuse them.
3. **Decorator computation** — fuse the inlined grouped variant with
   `viewDecoration` mixin by relaxing the `fields` prop requirement.
4. **Row store actions** — `updateRowValue`, `moveRow`, etc. could be
   built on a common adapter that each grid provides (similar to how
   `rowLifecycle.js` works for create/delete).
5. **Realtime event handler factory** — `handleRealtimeRowUpdated /
   Created / Deleted` could be one factory parameterised on the grid's
   bucket model.

---

## Recent fixes worth noting (race / footgun fixes)

| Fix | Where |
|---|---|
| `deleteAllNonPrimaryFieldsFromTable` now properly awaits all deletes via `Promise.all` (was firing-and-forgetting, causing 409 races with subsequent `createField`). | `e2e-tests/fixtures/database/field.ts` |
| Add-row trailer was missing right + bottom borders (data rows draw them per-cell, but the trailer only has the id-lane cell). | `GridGroupedRowAdd.vue` |
| Outer wrapper for absolute positioning so `RecursiveWrapper` can apply wrapper decorations without losing position. | `GridGroupedRow.vue` |
| Drag-handle hover-reveal requires `hover()` before reading `boundingBox()` in E2E. | `e2e-tests/tests/database/grouped_grid_row_drag.spec.ts` |
| Context popover uses `MoveToBody` so the popover lives at body root, not inside the trigger — E2E selectors need to target globally. | `e2e-tests/tests/database/grouped_grid_search.spec.ts` |
| Head row was flex-shrinking column widths to fit viewport while the body canvas kept full widths → head and body columns drifted out of alignment. Set explicit `width: canvasWidth` on `.grid-grouped__head`. | `GridGrouped.vue` |
| `GridViewFieldDragging.up()` dispatched `"right of <field>"`, which the store action interprets in `order` index space. Primary-first sort puts the primary at visible position 0 regardless of its order, so "right of primary" landed the dragged field at the END visually. Now always sends `"left of <next visible field>"` and only falls back to `"right of last"` at the end of the list. Also affects flat. | `GridViewFieldDragging.vue` |
