/**
 * Grouped grid view Vuex module.
 *
 * Responsibility: keep the per-section row buckets consistent with BE
 * truth + the user's optimistic edits in flight. The render core
 * (`gridGroupedRender`) reads those buckets directly — no derivation
 * from global offsets, no re-bucketing per render. The flat
 * (no-group-by) grid stays on the legacy `store/view/grid.js` module
 * and is not touched by anything here.
 *
 * State shape:
 *   - `tree`            : { nodes: GroupNode[], fullyLoaded: boolean }
 *                         Source of truth for group structure + row
 *                         counts per section. Section pixel sizes are
 *                         derived from these counts.
 *   - `collapse`        : { mode: 'expand'|'collapse', paths: Path[] }
 *                         In 'expand' mode, `paths` is the collapsed
 *                         list; in 'collapse' mode it's the expanded
 *                         list.
 *   - `sectionRows`     : Map<sectionKey, Map<positionInSection, RowData>>
 *                         Per-section row buckets. A row at position N
 *                         of section X lives at
 *                         `sectionRows.get(X).get(N)`. Positions are
 *                         BE-truthful (matching the section's sorted
 *                         order at fetch time). Toggling collapse on
 *                         any other section does NOT touch these
 *                         buckets — that's the structural fix this
 *                         module exists to provide.
 *   - `rowIndex`        : Map<rowId, {sectionKey, position}>
 *                         O(1) reverse lookup, kept in lockstep with
 *                         every `sectionRows` mutation.
 *   - `sectionFetched`  : Map<sectionKey, Set<rangeKey>>
 *                         Per-section fetched position ranges, keyed
 *                         by `${startPosition}:${endPosition}` (end
 *                         exclusive). Used purely for fetch dedup.
 *   - `sectionInflight` : Map<sectionKey, Set<rangeKey>>
 *                         Like `sectionFetched` but for in-flight
 *                         requests. Cleared on request settle.
 *   - `pendingMutations`: Map<rowId, {patch, fromSectionKey?, ...}>
 *                         Optimistic edit overlay. The render core
 *                         applies `patch` to row data; structural
 *                         moves (group-by changes) are materialised
 *                         into `sectionRows` at edit time, so the
 *                         from/to bookkeeping here is purely for
 *                         rollback.
 *   - `viewport`        : { scrollTop, clientHeight }
 *                         Driven by the component on scroll. Used by
 *                         the render core to window the layout and by
 *                         `ensureRowsForViewport` to schedule fetches.
 *
 * Race resilience: an in-flight realtime event for a row that has a
 * pending optimistic edit does not collide because `sectionRows` is
 * BE-truthful (mutated by realtime + commit) while `pendingMutations`
 * is the user's overlay. The render core merges them at render time.
 */

import {
  pathKey,
  buildLayout,
  visibleSectionsInViewport,
} from '@baserow/modules/database/utils/gridGroupedRender'
import {
  prepareNewOldAndUpdateRequestValues,
  prepareRowMultiFieldUpdate,
  updateRowMetadataType,
} from '@baserow/modules/database/utils/row'
import {
  calculateSingleRowSearchMatches,
  getRowSortFunction,
} from '@baserow/modules/database/utils/view'
import { getDefaultSearchModeFromEnv } from '@baserow/modules/database/utils/search'
import {
  createRowOptimistically,
  deleteRowOptimistically,
  reapplyMatchFlags,
} from '@baserow/modules/database/utils/rowLifecycle'
import GridService from '@baserow/modules/database/services/view/grid'
import RowService from '@baserow/modules/database/services/row'

const COLLAPSE_MODE_EXPAND = 'expand'
const COLLAPSE_MODE_COLLAPSE = 'collapse'

// Block size used by the fetch coordinator. Matches what the BE
// happily returns in one response while keeping scrolling smooth.
const DEFAULT_BLOCK_SIZE = 120

const rangeKey = (start, end) => `${start}:${end}`

const ensureBucket = (map, key) => {
  let bucket = map.get(key)
  if (!bucket) {
    bucket = new Map()
    map.set(key, bucket)
  }
  return bucket
}

const ensureSet = (map, key) => {
  let set = map.get(key)
  if (!set) {
    set = new Set()
    map.set(key, set)
  }
  return set
}

// Build the standard `_` metadata block the shared `GridViewCell`
// component reads (persistentId, loading flags, search match state,
// …). The BE response doesn't include it, so we populate a safe
// default that mirrors what `populateRow` in the legacy store does.
const buildRowMeta = (row, existingMeta) => ({
  loading: false,
  fetching: false,
  fullyLoaded: true,
  matchFilters: true,
  matchSortings: true,
  matchSearch: true,
  fieldSearchMatches: [],
  selected: false,
  selectedFieldId: -1,
  selectedBy: [],
  persistentId: 'r' + row.id,
  ...(existingMeta ?? {}),
  ...(row._ ?? {}),
})

const withMeta = (row, existing) => ({
  ...(existing ?? {}),
  ...row,
  _: buildRowMeta(row, existing?._),
})

// Shift fetched/inflight ranges in response to a structural change
// (row inserted/removed at `position`). `delta` is +1 for insert, -1
// for remove. Ranges entirely before the change stay put; ranges
// entirely after shift; ranges spanning the change extend (insert) or
// shrink (remove) on the end side.
const shiftRangesInSet = (set, position, delta) => {
  if (!set || set.size === 0) return set
  const next = new Set()
  for (const key of set) {
    const [startStr, endStr] = key.split(':')
    const start = Number(startStr)
    const end = Number(endStr)
    if (end <= position) {
      next.add(key)
    } else if (start > position) {
      next.add(rangeKey(start + delta, end + delta))
    } else {
      // Spans `position`. Extend or shrink the end-side bound.
      const newEnd = end + delta
      if (newEnd > start) next.add(rangeKey(start, newEnd))
    }
  }
  return next
}

const shiftSectionRanges = (state, sectionKey, position, delta) => {
  const fetched = state.sectionFetched.get(sectionKey)
  if (fetched) {
    state.sectionFetched.set(
      sectionKey,
      shiftRangesInSet(fetched, position, delta)
    )
  }
  const inflight = state.sectionInflight.get(sectionKey)
  if (inflight) {
    state.sectionInflight.set(
      sectionKey,
      shiftRangesInSet(inflight, position, delta)
    )
  }
}

// In-place shift of every position > `pivot` (remove) or >= `pivot`
// (insert) inside a section bucket. Returns nothing; mutates `bucket`
// and `state.rowIndex` together so they stay in lockstep.
const shiftBucketPositions = (state, sectionKey, bucket, pivot, delta) => {
  // Snapshot entries — we mutate `bucket` mid-loop.
  const entries = [...bucket.entries()]
  // Sort by position so we shift in the right direction (descending
  // for +1 to avoid colliding with a slot we're about to write;
  // ascending for -1 for the same reason).
  entries.sort(([a], [b]) => (delta > 0 ? b - a : a - b))
  for (const [pos, row] of entries) {
    const inRange = delta > 0 ? pos >= pivot : pos > pivot
    if (!inRange) continue
    bucket.delete(pos)
    const newPos = pos + delta
    bucket.set(newPos, row)
    state.rowIndex.set(row.id, { sectionKey, position: newPos })
  }
}

export const state = () => ({
  // Identity
  gridId: null,
  groupByFields: [],
  // When `hideRowsNotMatchingSearch` is true and `activeSearchTerm` is
  // non-empty, fetch calls send the search query to the BE so only
  // matching rows come back (and row counts shrink accordingly). When
  // false (highlight-only) the search affects only client-side
  // `_.matchSearch` flags, not the bucket contents.
  activeSearchTerm: '',
  hideRowsNotMatchingSearch: false,
  // Pixel height of a single body row. Driven by view.row_height_size
  // (small=33, medium=55, large=99) — kept here so the layout/render
  // helpers receive it as a parameter, since the same module is
  // imported from contexts that don't have direct access to the
  // active view.
  rowHeight: 33,
  sortings: [],
  registry: null,

  // Tree
  tree: { nodes: [], fullyLoaded: false },

  // Collapse state
  collapse: { mode: COLLAPSE_MODE_EXPAND, paths: [] },

  // Per-section row buckets — source of truth for placement.
  sectionRows: new Map(),
  rowIndex: new Map(),

  // Per-section fetch tracking. Range keys are
  // `${startPosition}:${endPosition}` (end exclusive) within the
  // section's own positions, not BE global offsets.
  sectionFetched: new Map(),
  sectionInflight: new Map(),

  // Pending optimistic edits. Patch is applied as a render-time
  // overlay; structural moves are materialised into `sectionRows`
  // immediately, with from/to bookkeeping retained for rollback.
  pendingMutations: new Map(),

  // Viewport (component-driven)
  viewport: { scrollTop: 0, clientHeight: 0 },

  // Single-cell selection ({rowId, fieldId} | null). At most one cell
  // is "selected" at any time across the entire grid — clicking a new
  // cell unselects the previous. Section-agnostic, so survives moves.
  selectedCell: null,
})

export const mutations = {
  INIT(state, { gridId, groupByFields, sortings, collapseMode, registry }) {
    state.gridId = gridId ?? state.gridId
    if (groupByFields !== undefined) state.groupByFields = groupByFields
    if (sortings !== undefined) state.sortings = sortings
    if (collapseMode !== undefined) state.collapse.mode = collapseMode
    if (registry !== undefined) state.registry = registry
    state.collapse.paths = []
    state.tree = { nodes: [], fullyLoaded: false }
    state.sectionRows = new Map()
    state.rowIndex = new Map()
    state.sectionFetched = new Map()
    state.sectionInflight = new Map()
    state.pendingMutations = new Map()
    state.selectedCell = null
  },

  SET_GROUP_BY_FIELDS(state, fields) {
    state.groupByFields = fields
  },

  SET_ROW_HEIGHT(state, rowHeight) {
    if (Number.isFinite(rowHeight) && rowHeight > 0) {
      state.rowHeight = rowHeight
    }
  },

  SET_SEARCH(state, { activeSearchTerm, hideRowsNotMatchingSearch }) {
    if (activeSearchTerm !== undefined) {
      state.activeSearchTerm = activeSearchTerm
    }
    if (hideRowsNotMatchingSearch !== undefined) {
      state.hideRowsNotMatchingSearch = hideRowsNotMatchingSearch
    }
  },

  SET_TREE(state, tree) {
    state.tree = {
      nodes: tree.nodes ?? [],
      fullyLoaded: tree.fullyLoaded ?? false,
    }
  },

  // Replace contents of section bucket positions [startPosition,
  // startPosition + rows.length). Used by the fetch path. Overwrites
  // existing entries at those positions — the BE response is
  // authoritative for the range it covers.
  MERGE_SECTION_ROWS(state, { sectionKey, startPosition, rows }) {
    if (!Array.isArray(rows) || rows.length === 0) return
    const bucket = ensureBucket(state.sectionRows, sectionKey)
    rows.forEach((row, i) => {
      const position = startPosition + i
      const existing = bucket.get(position)
      const merged = withMeta(row, existing)
      // If this rowId was previously indexed elsewhere (re-fetch of a
      // row whose section changed remotely between fetches), drop the
      // stale entry so we don't leave a phantom in the old bucket.
      const prior = state.rowIndex.get(row.id)
      if (prior && (prior.sectionKey !== sectionKey || prior.position !== position)) {
        const priorBucket = state.sectionRows.get(prior.sectionKey)
        if (priorBucket && priorBucket.get(prior.position)?.id === row.id) {
          priorBucket.delete(prior.position)
        }
      }
      bucket.set(position, merged)
      state.rowIndex.set(row.id, { sectionKey, position })
    })
  },

  // Insert `row` at `position` of `sectionKey`, shifting existing
  // entries at positions >= `position` up by 1. Used by realtime
  // create + optimistic move-in.
  INSERT_ROW_INTO_SECTION(state, { sectionKey, position, row }) {
    const bucket = ensureBucket(state.sectionRows, sectionKey)
    shiftBucketPositions(state, sectionKey, bucket, position, +1)
    const existing = bucket.get(position)
    const merged = withMeta(row, existing)
    bucket.set(position, merged)
    state.rowIndex.set(row.id, { sectionKey, position })
    shiftSectionRanges(state, sectionKey, position, +1)
  },

  // Remove the row at `position` of `sectionKey` and shift positions
  // > `position` down by 1. Used by realtime delete + optimistic
  // move-out.
  REMOVE_ROW_FROM_SECTION(state, { sectionKey, position }) {
    const bucket = state.sectionRows.get(sectionKey)
    if (!bucket) return
    const removed = bucket.get(position)
    bucket.delete(position)
    if (removed) state.rowIndex.delete(removed.id)
    shiftBucketPositions(state, sectionKey, bucket, position, -1)
    shiftSectionRanges(state, sectionKey, position, -1)
  },

  // Atomic move. Carries out source-remove (with shift) and
  // target-insert (with shift) as a single mutation so the rowIndex
  // never points at a half-deleted state.
  MOVE_ROW_BETWEEN_SECTIONS(
    state,
    { rowId, fromSectionKey, fromPosition, toSectionKey, toPosition }
  ) {
    const fromBucket = state.sectionRows.get(fromSectionKey)
    if (!fromBucket) return
    const row = fromBucket.get(fromPosition)
    if (!row || row.id !== rowId) return

    // Source: remove + shift.
    fromBucket.delete(fromPosition)
    shiftBucketPositions(state, fromSectionKey, fromBucket, fromPosition, -1)
    shiftSectionRanges(state, fromSectionKey, fromPosition, -1)

    // Target: insert + shift.
    const toBucket = ensureBucket(state.sectionRows, toSectionKey)
    shiftBucketPositions(state, toSectionKey, toBucket, toPosition, +1)
    toBucket.set(toPosition, row)
    state.rowIndex.set(rowId, {
      sectionKey: toSectionKey,
      position: toPosition,
    })
    shiftSectionRanges(state, toSectionKey, toPosition, +1)
  },

  // Patch the `_.matchFilters` and `_.matchSortings` flags on the
  // row at the given id. Drives the "row has moved" warning the
  // flat grid also renders.
  SET_ROW_MATCH_FLAGS(state, { rowId, matchFilters, matchSortings }) {
    const idx = state.rowIndex.get(rowId)
    if (!idx) return
    const bucket = state.sectionRows.get(idx.sectionKey)
    const existing = bucket?.get(idx.position)
    if (!existing) return
    const next = {
      ...existing,
      _: {
        ...(existing._ ?? {}),
        ...(matchFilters !== undefined ? { matchFilters } : {}),
        ...(matchSortings !== undefined ? { matchSortings } : {}),
      },
    }
    bucket.set(idx.position, next)
  },

  // Replace whatever row is currently at `(sectionKey, position)`
  // with `newRow`, swapping the rowIndex entry from the old row id
  // to the new one. Atomic — used to reconcile an optimistic
  // placeholder (temp id, `_.loading=true`) with the BE-returned
  // row after a successful create.
  REPLACE_ROW_AT_POSITION(state, { sectionKey, position, newRow }) {
    const bucket = state.sectionRows.get(sectionKey)
    if (!bucket) return
    const existing = bucket.get(position)
    if (existing) state.rowIndex.delete(existing.id)
    const merged = { ...newRow, _: buildRowMeta(newRow, null) }
    bucket.set(position, merged)
    state.rowIndex.set(newRow.id, { sectionKey, position })
  },

  // Update row data in place — no structural change. Used by commit
  // of pending edits + same-section realtime updates.
  UPDATE_ROW_DATA(state, { rowId, patch }) {
    const idx = state.rowIndex.get(rowId)
    if (!idx) return
    const bucket = state.sectionRows.get(idx.sectionKey)
    if (!bucket) return
    const existing = bucket.get(idx.position)
    if (!existing) return
    const merged = withMeta({ ...existing, ...patch, id: rowId }, existing)
    bucket.set(idx.position, merged)
  },

  // Drop any sectionRows / fetch tracking for section keys that are
  // no longer in the tree. Called after `SET_TREE` so a removed group
  // doesn't keep ghost rows + ghost fetched ranges around.
  RECONCILE_SECTIONS(state, { validSectionKeys }) {
    const valid = new Set(validSectionKeys)
    for (const key of [...state.sectionRows.keys()]) {
      if (valid.has(key)) continue
      const bucket = state.sectionRows.get(key)
      if (bucket) {
        for (const row of bucket.values()) {
          state.rowIndex.delete(row.id)
        }
      }
      state.sectionRows.delete(key)
      state.sectionFetched.delete(key)
      state.sectionInflight.delete(key)
    }
  },

  // Adjust a node's rowCount by `delta`. Clamps at 0; never goes
  // negative.
  UPDATE_TREE_NODE_COUNT(state, { path, delta }) {
    const fields = state.groupByFields
    const target = pathKey(path, fields)
    for (const node of state.tree.nodes) {
      if (pathKey(node.path, fields) === target) {
        const next = (node.rowCount ?? node.row_count ?? 0) + delta
        node.rowCount = Math.max(0, next)
        return
      }
    }
  },

  // Insert a brand-new tree node. Pre-condition: a node with this
  // exact path does not already exist.
  INSERT_TREE_NODE(state, { node }) {
    const fields = state.groupByFields
    const targetKey = pathKey(node.path, fields.slice(0, node.depth + 1))
    if (
      state.tree.nodes.some(
        (n) =>
          n.depth === node.depth &&
          pathKey(n.path, fields.slice(0, n.depth + 1)) === targetKey
      )
    ) {
      return
    }
    state.tree.nodes.push(node)
  },

  TOGGLE_COLLAPSE(state, path) {
    const fields = state.groupByFields
    const target = pathKey(path, fields.slice(0, Object.keys(path).length))
    const idx = state.collapse.paths.findIndex(
      (p) => pathKey(p, fields.slice(0, Object.keys(p).length)) === target
    )
    if (idx >= 0) {
      state.collapse.paths.splice(idx, 1)
    } else {
      state.collapse.paths.push({ ...path })
    }
    // Per-section caches survive a collapse toggle — section
    // contents are invariant of which other groups are expanded.
  },

  // Flip into "all collapsed" / "all expanded" by switching the mode
  // and clearing the exception list. In mode `expand` the paths list
  // is the set of *collapsed* groups; in mode `collapse` it's the set
  // of *expanded* ones. So "all collapsed" = collapse + [] and
  // "all expanded" = expand + [].
  SET_COLLAPSE_MODE(state, mode) {
    state.collapse.mode = mode
    state.collapse.paths = []
  },

  // Re-sort the section's loaded rows by `sortFn` and reassign their
  // positions starting from the bucket's current first-loaded
  // position. The caller is responsible for confirming the bucket is
  // contiguous (i.e. positions form `[N, N+1, …, N+k]`); collapsing
  // gaps here would corrupt the BE-truthful position indices.
  RESORT_SECTION_BUCKET(state, { sectionKey, sortFn }) {
    const bucket = state.sectionRows.get(sectionKey)
    if (!bucket || bucket.size === 0) return
    const entries = [...bucket.entries()].sort(([a], [b]) => a - b)
    const firstLoadedPosition = entries[0][0]
    const rows = entries.map(([, row]) => row).sort(sortFn)
    const newBucket = new Map()
    rows.forEach((row, i) => {
      const position = firstLoadedPosition + i
      newBucket.set(position, row)
      state.rowIndex.set(row.id, { sectionKey, position })
    })
    state.sectionRows.set(sectionKey, newBucket)
  },

  SET_VIEWPORT(state, { scrollTop, clientHeight }) {
    state.viewport = { scrollTop, clientHeight }
  },

  SELECT_CELL(state, { rowId, fieldId }) {
    state.selectedCell = { rowId, fieldId }
  },

  CLEAR_CELL_SELECTION(state) {
    state.selectedCell = null
  },

  SET_PENDING_ROW(state, { rowId, mutation }) {
    const existing = state.pendingMutations.get(rowId) ?? {}
    state.pendingMutations.set(rowId, {
      ...existing,
      ...mutation,
      patch: { ...(existing.patch ?? {}), ...(mutation.patch ?? {}) },
    })
  },

  CLEAR_PENDING_ROW(state, rowId) {
    state.pendingMutations.delete(rowId)
  },

  MARK_SECTION_RANGE_INFLIGHT(state, { sectionKey, startPosition, endPosition }) {
    ensureSet(state.sectionInflight, sectionKey).add(
      rangeKey(startPosition, endPosition)
    )
  },

  MARK_SECTION_RANGE_FETCHED(state, { sectionKey, startPosition, endPosition }) {
    const key = rangeKey(startPosition, endPosition)
    ensureSet(state.sectionFetched, sectionKey).add(key)
    state.sectionInflight.get(sectionKey)?.delete(key)
  },

  CLEAR_SECTION_RANGE_INFLIGHT(state, { sectionKey, startPosition, endPosition }) {
    state.sectionInflight
      .get(sectionKey)
      ?.delete(rangeKey(startPosition, endPosition))
  },

  // Wipe both fetched and inflight bookkeeping for a section. Used
  // when sort changes invalidate positions (section contents stay
  // valid keys-wise but positions are no longer trustworthy).
  CLEAR_SECTION_TRACKING(state, sectionKey) {
    state.sectionFetched.delete(sectionKey)
    state.sectionInflight.delete(sectionKey)
    const bucket = state.sectionRows.get(sectionKey)
    if (bucket) {
      for (const row of bucket.values()) state.rowIndex.delete(row.id)
      state.sectionRows.delete(sectionKey)
    }
  },
}

/**
 * Compute the leaf-level group path (depth = groupByFields.length) for
 * a row, going through each field type's `getGroupValueFromRowValue` so
 * row-form values (e.g. `{id, value, color}` for single-select) become
 * group-form values (just `id`).
 */
const leafPathForRow = (row, fields, registry) => {
  const path = {}
  for (const f of fields) {
    const key = `field_${f.id}`
    const fieldType = registry.get('field', f.type)
    path[key] = fieldType.getGroupValueFromRowValue(f, row[key])
  }
  return path
}

const leafKeyForRow = (row, fields, registry) =>
  pathKey(leafPathForRow(row, fields, registry), fields)

/**
 * Walk from depth-0 up to depth-(maxDepth) and apply `delta` to every
 * ancestor node along the path.
 */
const adjustAncestorCounts = (commit, leafPath, fields, delta) => {
  for (let d = 0; d < fields.length; d++) {
    const path = {}
    for (let i = 0; i <= d; i++) {
      const f = fields[i]
      path[`field_${f.id}`] = leafPath[`field_${f.id}`]
    }
    commit('UPDATE_TREE_NODE_COUNT', { path, delta })
  }
}

/**
 * For an optimistic group-by edit, ensure every depth has a matching
 * tree node before adjusting counts.
 */
const ensureTreeNodesForPath = (state, commit, leafPath, fields) => {
  const treeKeyAt = (depth) =>
    pathKey(
      Object.fromEntries(
        fields
          .slice(0, depth + 1)
          .map((f) => [`field_${f.id}`, leafPath[`field_${f.id}`]])
      ),
      fields.slice(0, depth + 1)
    )
  for (let d = 0; d < fields.length; d++) {
    const key = treeKeyAt(d)
    const exists = state.tree.nodes.some(
      (n) => n.depth === d && pathKey(n.path, fields.slice(0, d + 1)) === key
    )
    if (exists) continue
    const path = {}
    for (let i = 0; i <= d; i++) {
      const f = fields[i]
      path[`field_${f.id}`] = leafPath[`field_${f.id}`]
    }
    commit('INSERT_TREE_NODE', {
      node: { path, depth: d, rowCount: 0 },
    })
  }
}

const groupByValuesChanged = (before, after, fields, registry) =>
  leafKeyForRow(before, fields, registry) !==
  leafKeyForRow(after, fields, registry)

// Translate a BE group-tree node to the shape `buildLayout` expects.
const normaliseBeTreeNode = (beNode, groupByFields) => {
  let depth = beNode.depth
  if (typeof depth !== 'number') {
    depth =
      groupByFields.reduce(
        (acc, f) => acc + (`field_${f.id}` in beNode.path ? 1 : 0),
        0
      ) - 1
  }
  return {
    path: beNode.path,
    depth,
    rowCount: beNode.row_count ?? beNode.rowCount ?? 0,
    children_count: beNode.children_count ?? null,
  }
}

const flattenBeTree = (beNodes, groupByFields, out = []) => {
  if (!Array.isArray(beNodes)) return out
  for (const node of beNodes) {
    out.push(normaliseBeTreeNode(node, groupByFields))
    if (Array.isArray(node.children) && node.children.length > 0) {
      flattenBeTree(node.children, groupByFields, out)
    }
  }
  return out
}

// A path is a leaf iff it contains an entry for every group-by field.
const isLeafPath = (path, fields) => {
  for (const f of fields) {
    if (!(`field_${f.id}` in path)) return false
  }
  return true
}

// Build the `collapsed_groups` query param the BE expects.
//
// Mode 'expand' (paths = COLLAPSED list): BE excludes rows matching
// any path — OR-semantics is exactly right here, because we want to
// exclude rows under ANY collapsed ancestor. Send paths as-is.
//
// Mode 'collapse' (paths = EXPANDED list): BE keeps rows matching
// any path. OR-semantics would over-include: a depth-0 path {A}
// matches all A rows regardless of whether the user has expanded any
// A.B sub-group. Our local layout treats A.B as visible only when
// {A.B} is explicitly in `paths`, so we send ONLY leaf paths to the
// BE — OR(leaves) equals the intersection of all ancestor expansions
// our layout treats as visible.
const collapsedGroupsParam = (state) => {
  const paths = state.collapse.paths
  if (paths.length === 0) return ''
  const fields = state.groupByFields
  if (state.collapse.mode === COLLAPSE_MODE_COLLAPSE) {
    const leafPaths = paths.filter((p) => isLeafPath(p, fields))
    if (leafPaths.length === 0) return ''
    return JSON.stringify(leafPaths.map((p) => ({ ...p })))
  }
  return JSON.stringify(paths.map((p) => ({ ...p })))
}

// Sorted insertion position for `row` inside the target section's
// bucket. Returns `null` when we can't place the row with confidence
// and want the next viewport refetch to handle it.
//
// Confidence rules (the caller has already bumped section.rowCount
// by +1, so newRowCount here is the post-increment count):
//
//   1. Mid-bucket: at least one loaded row sorts before AND one
//      sorts after — insert at the first row sorting after. Safe.
//   2. Before every loaded row, AND the bucket starts at position 0:
//      no unloaded positions exist before the first loaded row, so
//      the true position is 0. Safe.
//   3. After every loaded row, AND the bucket extends to the
//      pre-increment last position (newRowCount - 2): no unloaded
//      gaps remain before the new slot, so the true position is
//      newRowCount - 1. Safe.
//   4. Otherwise: there's unloaded territory adjacent to where we'd
//      insert — bail out (`null`) and let the refetch reconcile.
const findSortedInsertionPosition = (bucket, row, sortFn, newRowCount) => {
  if (!bucket || bucket.size === 0) return null
  const entries = [...bucket.entries()].sort(([a], [b]) => a - b)
  const firstLoadedPos = entries[0][0]
  const lastLoadedPos = entries[entries.length - 1][0]

  let sawSmaller = false
  for (const [pos, existing] of entries) {
    const cmp = sortFn(row, existing)
    if (cmp < 0) {
      if (sawSmaller) {
        // Rule 1: mid-bucket — confident.
        return pos
      }
      // Sorts before every loaded row so far. Confident only if we
      // know nothing is loaded before position 0 (rule 2).
      return firstLoadedPos === 0 ? 0 : null
    }
    sawSmaller = true
  }
  // Sorts after every loaded row. Confident only if the bucket
  // already extends to the pre-increment last position (rule 3).
  if (
    Number.isFinite(newRowCount) &&
    lastLoadedPos === newRowCount - 2
  ) {
    return newRowCount - 1
  }
  return null
}

// Return the row immediately after `sourceRowId` within the same
// section bucket — the next loaded position. Used to compute
// `beforeId` for "insert below" / "duplicate" so the BE places the
// new row between source and its visual neighbour.
const findNextRowInSection = (state, sourceRowId) => {
  const idx = state.rowIndex.get(sourceRowId)
  if (!idx) return null
  const bucket = state.sectionRows.get(idx.sectionKey)
  if (!bucket) return null
  let nextPos = Infinity
  let nextRow = null
  for (const [pos, row] of bucket.entries()) {
    if (pos > idx.position && pos < nextPos) {
      nextPos = pos
      nextRow = row
    }
  }
  return nextRow
}

// Build the supplied-values map for a duplicate: every non-read-only
// field's value run through `prepareValueForDuplicate` so the field
// type can clear values that shouldn't carry over (autonumber, etc.).
const buildDuplicateValuesFromRow = (sourceRow, fields, registry) => {
  const out = {}
  for (const f of fields) {
    const key = `field_${f.id}`
    if (!(key in sourceRow)) continue
    const fieldType = registry.get('field', f.type)
    if (fieldType.isReadOnlyField?.(f)) continue
    out[key] = fieldType.prepareValueForDuplicate
      ? fieldType.prepareValueForDuplicate(f, sourceRow[key])
      : sourceRow[key]
  }
  return out
}

// Walk the layout we'd derive from current tree+collapse and find the
// row section whose path key matches `sectionKey`. Returns null if not
// found (section disappeared between schedule + run).
const findSectionInLayout = (state, sectionKey) => {
  const layout = buildLayout({
    nodes: state.tree.nodes,
    collapse: state.collapse,
    fields: state.groupByFields,
    rowHeight: state.rowHeight,
  })
  for (const item of layout.items) {
    if (item.type !== 'rowSection') continue
    if (pathKey(item.path, state.groupByFields) === sectionKey) return item
  }
  return null
}

export const actions = {
  /**
   * Configure the module for a specific view and trigger the initial
   * tree fetch. Called once when the grouped view mounts.
   */
  async initialize(
    { commit, dispatch },
    { gridId, groupByFields, sortings, collapseMode, registry }
  ) {
    commit('INIT', {
      gridId,
      groupByFields,
      sortings,
      collapseMode,
      registry,
    })
    await dispatch('fetchTree')
  },

  /**
   * Fetch the group tree (nodes + row counts; no row data). After the
   * tree lands, reconcile section caches: sections that no longer
   * exist in the tree get their buckets + tracking dropped.
   */
  async fetchTree({ state, commit }) {
    if (state.gridId === null) return
    const search =
      state.hideRowsNotMatchingSearch && state.activeSearchTerm
        ? state.activeSearchTerm
        : ''
    const { data } = await GridService(this.$client).fetchGroupTree({
      gridId: state.gridId,
      search,
    })
    const nodes = flattenBeTree(
      data.nodes ?? data.results ?? [],
      state.groupByFields
    )
    commit('SET_TREE', { nodes, fullyLoaded: !!data.fully_loaded })
    // Reconcile: keep only buckets whose section key still exists in
    // the new tree.
    const fields = state.groupByFields
    const validSectionKeys = nodes
      .filter((n) => n.depth === fields.length - 1)
      .map((n) => pathKey(n.path, fields))
    commit('RECONCILE_SECTIONS', { validSectionKeys })
  },

  /**
   * Fetch a contiguous range of rows for a specific section and merge
   * them into the bucket. The BE call uses the existing /rows/
   * endpoint with global offset/limit; we translate section position
   * → global offset via the layout's `firstGlobalRowOffset`.
   *
   * The fetch is capped to the section's row count so the response
   * never bleeds into the next section (which would corrupt the
   * adjacent bucket).
   */
  async fetchSectionRows(
    { state, commit, rootGetters },
    { sectionKey, startPosition, count }
  ) {
    if (state.gridId === null) return
    const section = findSectionInLayout(state, sectionKey)
    if (!section) return
    const cappedCount = Math.min(
      count,
      Math.max(0, section.rowCount - startPosition)
    )
    if (cappedCount <= 0) return
    const endPosition = startPosition + cappedCount
    const globalOffset = section.firstGlobalRowOffset + startPosition

    const groupBy = (state.groupByFields ?? [])
      .map((f) => `field_${f.id}`)
      .join(',')
    const search =
      state.hideRowsNotMatchingSearch && state.activeSearchTerm
        ? state.activeSearchTerm
        : ''
    const { data } = await GridService(this.$client).fetchRows({
      gridId: state.gridId,
      offset: globalOffset,
      limit: cappedCount,
      groupBy,
      collapsedGroups: collapsedGroupsParam(state),
      collapsedGroupsMode: state.collapse.mode,
      search,
    })
    const rows = Array.isArray(data.results) ? data.results : []
    if (rows.length > 0) {
      commit('MERGE_SECTION_ROWS', {
        sectionKey,
        startPosition,
        rows,
      })
      // Apply the active search to the freshly merged rows. We mutate
      // `row._.matchSearch` / `_.fieldSearchMatches` directly on the
      // bucket entries (same reference the cells render against), so
      // the highlights appear without bouncing through the flat
      // store. In hide-mode the BE has already filtered these to
      // matches, but we still need the per-field-match indices for
      // highlighting individual cells.
      if (state.activeSearchTerm) {
        const fields = rootGetters['field/getAll'] ?? []
        const registry = state.registry ?? this.$registry
        const searchMode = getDefaultSearchModeFromEnv(this.$config)
        const bucket = state.sectionRows.get(sectionKey)
        for (let i = 0; i < rows.length; i++) {
          const row = bucket?.get(startPosition + i)
          if (!row?._) continue
          const { matchSearch, fieldSearchMatches } =
            calculateSingleRowSearchMatches(
              row,
              state.activeSearchTerm,
              state.hideRowsNotMatchingSearch,
              fields,
              registry,
              searchMode
            )
          row._.matchSearch = matchSearch
          row._.fieldSearchMatches = [...fieldSearchMatches]
        }
      }
    }
    return { sectionKey, startPosition, endPosition, count: rows.length }
  },

  /**
   * For every section that overlaps the current viewport, fetch any
   * block-aligned uncovered ranges. One request per section per
   * uncovered block; dedup'd against `sectionFetched` +
   * `sectionInflight`.
   */
  async ensureRowsForViewport(
    { state, commit, dispatch },
    { blockSize = DEFAULT_BLOCK_SIZE, padding = null } = {}
  ) {
    if (state.gridId === null) return
    const layout = buildLayout({
      nodes: state.tree.nodes,
      collapse: state.collapse,
      fields: state.groupByFields,
      rowHeight: state.rowHeight,
    })
    if (!layout.totalRowCount) return
    const pad = padding ?? state.viewport.clientHeight
    const widened = {
      scrollTop: Math.max(0, state.viewport.scrollTop - pad),
      clientHeight: state.viewport.clientHeight + 2 * pad,
    }
    const ranges = visibleSectionsInViewport(
      layout,
      widened,
      state.groupByFields,
      state.rowHeight
    )
    const pending = []
    for (const range of ranges) {
      const blockStart =
        Math.floor(range.startPosition / blockSize) * blockSize
      const blockEnd = Math.ceil(range.endPosition / blockSize) * blockSize
      for (let pos = blockStart; pos < blockEnd; pos += blockSize) {
        const cappedEnd = Math.min(pos + blockSize, range.rowCount)
        if (cappedEnd <= pos) break
        const key = rangeKey(pos, cappedEnd)
        const fetched = state.sectionFetched.get(range.sectionKey)
        const inflight = state.sectionInflight.get(range.sectionKey)
        if (fetched?.has(key)) continue
        if (inflight?.has(key)) continue
        commit('MARK_SECTION_RANGE_INFLIGHT', {
          sectionKey: range.sectionKey,
          startPosition: pos,
          endPosition: cappedEnd,
        })
        pending.push(
          dispatch('fetchSectionRows', {
            sectionKey: range.sectionKey,
            startPosition: pos,
            count: cappedEnd - pos,
          })
            .then(() =>
              commit('MARK_SECTION_RANGE_FETCHED', {
                sectionKey: range.sectionKey,
                startPosition: pos,
                endPosition: cappedEnd,
              })
            )
            .catch(() =>
              commit('CLEAR_SECTION_RANGE_INFLIGHT', {
                sectionKey: range.sectionKey,
                startPosition: pos,
                endPosition: cappedEnd,
              })
            )
        )
      }
    }
    if (pending.length === 0) return
    await Promise.all(pending)
  },

  /**
   * Action wrapper around `SELECT_CELL`. Dispatch this instead of
   * committing the mutation directly: when the user moves selection
   * from one row to another, the previous row may have a pending
   * "doesn't match filters" / "row has moved" warning (set by the
   * post-update match-flag re-eval), and the flat grid's standard
   * behaviour is to actually drop / reposition such rows once they
   * lose their selection. The dispatch order is: capture previous
   * row id → commit the selection change → refresh the previous
   * row (async).
   */
  async selectCell({ state, commit, dispatch }, { rowId, fieldId }) {
    const prevRowId = state.selectedCell?.rowId
    commit('SELECT_CELL', { rowId, fieldId })
    if (prevRowId != null && prevRowId !== rowId) {
      await dispatch('refreshRowAfterChange', { rowId: prevRowId })
    }
  },

  /**
   * Action wrapper around `CLEAR_CELL_SELECTION`; same rationale as
   * `selectCell` — the row that just lost selection needs to be
   * re-checked against the view's filters/sortings.
   */
  async clearCellSelection({ state, commit, dispatch }) {
    const prevRowId = state.selectedCell?.rowId
    commit('CLEAR_CELL_SELECTION')
    if (prevRowId != null) {
      await dispatch('refreshRowAfterChange', { rowId: prevRowId })
    }
  },

  /**
   * Apply the view's filters/sortings to a single row that just
   * lost its cell selection:
   *
   *   - `matchFilters === false` (or `matchSearch === false`):
   *     remove the row from its section bucket and decrement the
   *     tree counts for every ancestor. The row stays in the BE; we
   *     just hide it from the current view, matching how the flat
   *     grid drops rows that no longer satisfy the filter set after
   *     an edit.
   *   - `matchSortings === false`: refetch the row's section so it
   *     comes back at its BE-truth sorted position.
   *   - Otherwise: no-op.
   *
   * The match flags themselves come from `reapplyMatchFlags`, which
   * runs after a successful row update — so this action just acts on
   * the flags that are already on the row meta.
   */
  /**
   * Apply a row-metadata patch (comments count, presence, etc.) to the
   * row in its section bucket. Mirrors flat's `updateRowMetadata`.
   * Realtime metadata events arrive through viewTypes; the row
   * reference lives in `sectionRows` for grouped, so we mutate it
   * there.
   */
  updateRowMetadata(
    { state },
    { rowId, rowMetadataType, updateFunction }
  ) {
    const idx = state.rowIndex.get(rowId)
    if (!idx) return
    const row = state.sectionRows.get(idx.sectionKey)?.get(idx.position)
    if (!row) return
    updateRowMetadataType(row, rowMetadataType, updateFunction)
  },

  /**
   * Marks a field id on the row's `_.selectedBy` list. The presence
   * overlay rendered by `GridViewCell` reads this list to draw the
   * "another user is editing" border, and the flag also keeps the
   * row visible while at least one cell remains selected. We mutate
   * the row reference directly (same as the flat store's
   * `ADD_ROW_SELECTED_BY` mutation): grouped rows share the `_`
   * object with the layout items, so the reactivity is identical.
   */
  addRowSelectedBy(_ctx, { row, field }) {
    if (!row?._?.selectedBy) return
    if (!row._.selectedBy.includes(field.id)) {
      row._.selectedBy.push(field.id)
    }
  },
  /**
   * Inverse of `addRowSelectedBy` plus a match-flag re-evaluation so
   * the row's "has moved / doesn't match filters" warning catches up
   * after the cell is unselected. Flat refetches the row from BE; we
   * recompute the flags locally against the row's section, which is
   * enough for the warning to render.
   */
  async removeRowSelectedBy(
    { dispatch },
    { row, field }
  ) {
    if (row?._?.selectedBy) {
      const i = row._.selectedBy.indexOf(field.id)
      if (i > -1) row._.selectedBy.splice(i, 1)
    }
    await dispatch('refreshRowAfterChange', { rowId: row.id })
  },

  async refreshRowAfterChange({ state, commit, dispatch }, { rowId }) {
    const idx = state.rowIndex.get(rowId)
    if (!idx) return
    const bucket = state.sectionRows.get(idx.sectionKey)
    const row = bucket?.get(idx.position)
    const meta = row?._
    if (!meta) return
    const fields = state.groupByFields
    const registry = state.registry

    if (meta.matchFilters === false || meta.matchSearch === false) {
      if (registry && fields.length > 0) {
        const leafPath = leafPathForRow(row, fields, registry)
        adjustAncestorCounts(commit, leafPath, fields, -1)
      }
      commit('REMOVE_ROW_FROM_SECTION', {
        sectionKey: idx.sectionKey,
        position: idx.position,
      })
      return
    }

    if (meta.matchSortings === false) {
      commit('CLEAR_SECTION_TRACKING', idx.sectionKey)
      await dispatch('ensureRowsForViewport')
    }
  },

  /**
   * Flip the collapse state for a path, then re-fetch the tree (row
   * counts of newly-visible deeper subtrees may not be in local state).
   * Per-section buckets survive untouched — collapse doesn't move any
   * row out of its section.
   */
  async toggleCollapse({ commit, dispatch }, path) {
    commit('TOGGLE_COLLAPSE', path)
    await dispatch('fetchTree')
  },

  /**
   * Update the active search term + hide-mode in the grouped store.
   * In hide-mode (and a non-empty search) we structurally refetch
   * the tree and any visible sections so the row counts + buckets
   * reflect only matching rows. In highlight-mode the BE still
   * returns every row; the cell highlights come from the per-row
   * `_.matchSearch` flags that `GridGrouped.vue` already refreshes
   * via its `activeSearchTerm` watcher.
   */
  async setActiveSearch(
    { state, commit, dispatch },
    { activeSearchTerm, hideRowsNotMatchingSearch }
  ) {
    const prevSearch = state.activeSearchTerm
    const prevHide = state.hideRowsNotMatchingSearch
    commit('SET_SEARCH', { activeSearchTerm, hideRowsNotMatchingSearch })
    const next = state.activeSearchTerm
    const nextHide = state.hideRowsNotMatchingSearch
    const wasHideEffective = prevHide && prevSearch
    const isHideEffective = nextHide && next
    // Refetch only when the BE-visible row set actually changes:
    //   - switching into or out of hide-mode while a search is set
    //   - changing the search string while in hide-mode
    if (
      isHideEffective !== wasHideEffective ||
      (isHideEffective && next !== prevSearch)
    ) {
      for (const sectionKey of [...state.sectionRows.keys()]) {
        commit('CLEAR_SECTION_TRACKING', sectionKey)
      }
      await dispatch('fetchTree')
      await dispatch('ensureRowsForViewport')
    }
  },

  /**
   * Set every group's collapse state in one shot. Re-fetches the tree
   * so the BE returns row counts consistent with the new mode (the
   * counts are scoped to visible-only rows in some configurations).
   */
  async setCollapsedAll({ commit, dispatch }, { collapsed }) {
    commit('SET_COLLAPSE_MODE', collapsed ? 'collapse' : 'expand')
    await dispatch('fetchTree')
    await dispatch('ensureRowsForViewport')
  },

  /**
   * Invalidate every section's loaded rows + fetch tracking and pull
   * a fresh tree. Used when the view's filters/sortings change —
   * group sizes shift and the rows the user is currently looking at
   * may no longer match the view. Mirrors the flat grid's "throw out
   * the buffer + refetch by scroll position" reaction to view-config
   * changes.
   */
  async refreshForViewConfigChange(
    { state, commit, dispatch },
    { sortings, groupByFields } = {}
  ) {
    if (sortings !== undefined) state.sortings = sortings
    if (groupByFields !== undefined) {
      commit('SET_GROUP_BY_FIELDS', groupByFields)
      // Group-by structure changed (different fields or reordered):
      // the existing tree and section buckets are keyed on the old
      // groupByFields and no longer make sense. Reset everything
      // structural before refetching.
      state.tree = { nodes: [], fullyLoaded: false }
      state.sectionRows = new Map()
      state.rowIndex = new Map()
      state.sectionFetched = new Map()
      state.sectionInflight = new Map()
      state.pendingMutations = new Map()
    } else {
      // Drop every section's bucket + tracking. The next
      // `ensureRowsForViewport` will refetch what's currently in view.
      for (const sectionKey of [...state.sectionRows.keys()]) {
        commit('CLEAR_SECTION_TRACKING', sectionKey)
      }
    }
    await dispatch('fetchTree')
    await dispatch('ensureRowsForViewport')
  },

  /**
   * Apply an optimistic edit to a row. If the edit changes a group-by
   * value the row is structurally moved between section buckets right
   * now, tree counts shift to match, and bookkeeping is saved on the
   * pending entry for rollback.
   *
   * Non-group-by edits only write the patch; the render core overlays
   * it on the cached row.
   */
  optimisticEditRow({ state, commit }, { rowId, values, fields: allFields }) {
    const groupFields = state.groupByFields
    const registry = state.registry
    if (!registry || groupFields.length === 0) {
      commit('SET_PENDING_ROW', { rowId, mutation: { patch: { ...values } } })
      return
    }
    const idx = state.rowIndex.get(rowId)
    if (!idx) {
      commit('SET_PENDING_ROW', { rowId, mutation: { patch: { ...values } } })
      return
    }
    const bucket = state.sectionRows.get(idx.sectionKey)
    const cached = bucket?.get(idx.position) ?? {}
    const pendingEntry = state.pendingMutations.get(rowId)
    const before = { ...cached, ...(pendingEntry?.patch ?? {}) }
    const after = { ...before, ...values }

    if (!groupByValuesChanged(before, after, groupFields, registry)) {
      commit('SET_PENDING_ROW', { rowId, mutation: { patch: { ...values } } })
      return
    }

    const oldLeaf = leafPathForRow(before, groupFields, registry)
    const newLeaf = leafPathForRow(after, groupFields, registry)
    const newKey = pathKey(newLeaf, groupFields)

    // Tree: -1 on every ancestor of the old leaf, +1 on every
    // ancestor of the new leaf (creating tree nodes as needed).
    adjustAncestorCounts(commit, oldLeaf, groupFields, -1)
    ensureTreeNodesForPath(state, commit, newLeaf, groupFields)
    adjustAncestorCounts(commit, newLeaf, groupFields, +1)

    // Snapshot the row before we mutate the source bucket — needed
    // for the rollback path when we only remove and don't insert.
    const rowSnapshot = bucket?.get(idx.position)
      ? { ...bucket.get(idx.position) }
      : null

    // Decide the target position. When fields are supplied, ask the
    // BE-equivalent sort function for a confident slot in the target
    // bucket; null means "too uncertain — skip the insert and let
    // the next refetch place it correctly".
    const newSection = findSectionInLayout(state, newKey)
    const newBucket = state.sectionRows.get(newKey)
    let targetPosition = null
    if (allFields && allFields.length > 0) {
      const sortFn = getRowSortFunction(
        registry,
        state.sortings ?? [],
        allFields,
        groupFields
      )
      const newRowCount = newSection?.rowCount ?? 0
      targetPosition = findSortedInsertionPosition(
        newBucket,
        after,
        sortFn,
        newRowCount
      )
    } else if (newSection) {
      // No fields → caller can't sort. Best-effort append at the new
      // section's last position.
      targetPosition = Math.max(0, newSection.rowCount - 1)
    }

    if (targetPosition !== null) {
      commit('MOVE_ROW_BETWEEN_SECTIONS', {
        rowId,
        fromSectionKey: idx.sectionKey,
        fromPosition: idx.position,
        toSectionKey: newKey,
        toPosition: targetPosition,
      })
    } else {
      // Confident sort position unknown — remove from source only.
      // The growing target.rowCount + shrinking source range will
      // make `ensureRowsForViewport`'s block-aligned dedup miss its
      // cached range key on the next tick, triggering a refetch that
      // brings the row into the target bucket at its true position.
      commit('REMOVE_ROW_FROM_SECTION', {
        sectionKey: idx.sectionKey,
        position: idx.position,
      })
    }

    commit('SET_PENDING_ROW', {
      rowId,
      mutation: {
        patch: { ...values },
        fromPath: oldLeaf,
        fromSectionKey: idx.sectionKey,
        fromPosition: idx.position,
        fromRowSnapshot: rowSnapshot,
        toPath: newLeaf,
        toSectionKey: newKey,
        toPosition: targetPosition,
      },
    })
  },

  /**
   * BE PATCH succeeded — write the response into the row's bucket and
   * clear pending. If the BE's idea of the row's section disagrees
   * with our optimistic move (rare: user typed value that BE corrected
   * to a different group), structurally move to the BE's group.
   */
  commitPendingEdit({ state, commit }, { rowId, beRow }) {
    const fields = state.groupByFields
    const registry = state.registry
    const idx = state.rowIndex.get(rowId)
    if (!beRow) {
      commit('CLEAR_PENDING_ROW', rowId)
      return
    }
    if (!idx || !registry || fields.length === 0) {
      commit('UPDATE_ROW_DATA', { rowId, patch: beRow })
      commit('CLEAR_PENDING_ROW', rowId)
      return
    }
    const beLeaf = leafPathForRow(beRow, fields, registry)
    const beKey = pathKey(beLeaf, fields)
    if (beKey !== idx.sectionKey) {
      // BE says a different group than where we optimistically put
      // it. Move structurally, fixing up tree counts. The row is
      // structurally in `idx.sectionKey` — its data may still match
      // the pre-edit values, so we use the pending entry's `toPath`
      // (the optimistic target leaf) for the -1 if available, falling
      // back to the row's field values.
      const pending = state.pendingMutations.get(rowId)
      const currentLeaf =
        pending?.toPath ??
        (() => {
          const r = state.sectionRows.get(idx.sectionKey)?.get(idx.position)
          return r ? leafPathForRow(r, fields, registry) : null
        })()
      if (currentLeaf) adjustAncestorCounts(commit, currentLeaf, fields, -1)
      ensureTreeNodesForPath(state, commit, beLeaf, fields)
      adjustAncestorCounts(commit, beLeaf, fields, +1)
      const beSection = findSectionInLayout(state, beKey)
      const targetPosition = beSection
        ? Math.max(0, beSection.rowCount - 1)
        : 0
      commit('MOVE_ROW_BETWEEN_SECTIONS', {
        rowId,
        fromSectionKey: idx.sectionKey,
        fromPosition: idx.position,
        toSectionKey: beKey,
        toPosition: targetPosition,
      })
    }
    commit('UPDATE_ROW_DATA', { rowId, patch: beRow })
    commit('CLEAR_PENDING_ROW', rowId)
  },

  /**
   * BE PATCH failed — reverse the structural move from
   * `optimisticEditRow` (if any) and clear pending.
   */
  rollbackPendingEdit({ state, commit }, { rowId }) {
    const pending = state.pendingMutations.get(rowId)
    if (!pending) return
    const fields = state.groupByFields
    if (pending.fromPath && pending.toPath) {
      // Reverse tree counts unconditionally — they were bumped in
      // both branches of the optimistic path.
      adjustAncestorCounts(commit, pending.toPath, fields, -1)
      adjustAncestorCounts(commit, pending.fromPath, fields, +1)

      if (pending.toPosition !== null && pending.toPosition !== undefined) {
        // Row was structurally moved to target — reverse the move.
        const idx = state.rowIndex.get(rowId)
        if (idx && idx.sectionKey === pending.toSectionKey) {
          commit('MOVE_ROW_BETWEEN_SECTIONS', {
            rowId,
            fromSectionKey: pending.toSectionKey,
            fromPosition: idx.position,
            toSectionKey: pending.fromSectionKey,
            toPosition: pending.fromPosition,
          })
        }
      } else if (pending.fromRowSnapshot) {
        // Row was only removed from source (sort uncertain) — put
        // it back at its original position from the snapshot.
        commit('INSERT_ROW_INTO_SECTION', {
          sectionKey: pending.fromSectionKey,
          position: pending.fromPosition,
          row: pending.fromRowSnapshot,
        })
      }
    }
    commit('CLEAR_PENDING_ROW', rowId)
  },

  /**
   * Realtime event: a row was updated server-side. If the group-by
   * fields changed, structurally move the row + adjust tree counts.
   * Else just update data in place.
   *
   * Pending overlay is preserved — the user's in-flight edit stays
   * applied on top.
   */
  async handleRealtimeRowUpdated(
    { state, commit, dispatch },
    { row, fields: tableFields }
  ) {
    const fields = state.groupByFields
    const registry = state.registry
    const rowId = row.id
    const idx = state.rowIndex.get(rowId)
    if (!idx) {
      // We don't have the row in any bucket — nothing to do.
      // Lazy refetch will pick it up if the user scrolls there.
      return
    }
    const bucket = state.sectionRows.get(idx.sectionKey)
    const existing = bucket?.get(idx.position)
    if (!existing) return

    let sectionChanged = false
    if (registry && fields.length > 0) {
      const before = existing
      const after = { ...existing, ...row }
      if (groupByValuesChanged(before, after, fields, registry)) {
        sectionChanged = true
        const oldLeaf = leafPathForRow(before, fields, registry)
        const newLeaf = leafPathForRow(after, fields, registry)
        const newKey = pathKey(newLeaf, fields)
        adjustAncestorCounts(commit, oldLeaf, fields, -1)
        ensureTreeNodesForPath(state, commit, newLeaf, fields)
        adjustAncestorCounts(commit, newLeaf, fields, +1)
        const newSection = findSectionInLayout(state, newKey)
        const targetPosition = newSection
          ? Math.max(0, newSection.rowCount - 1)
          : 0
        commit('MOVE_ROW_BETWEEN_SECTIONS', {
          rowId,
          fromSectionKey: idx.sectionKey,
          fromPosition: idx.position,
          toSectionKey: newKey,
          toPosition: targetPosition,
        })
      }
    }
    commit('UPDATE_ROW_DATA', { rowId, patch: row })

    // A `row.order` change with no group-by change means the row was
    // re-positioned within its section (manual reorder, undo of a
    // move, backend re-rank). Apply locally by re-sorting the loaded
    // slice — no need to refetch, the realtime payload already has
    // the new state. We only do this if the bucket is contiguous;
    // otherwise (sparse, multi-chunk) collapsing the gaps would
    // break the BE position indices and we fall back to invalidate
    // + refetch.
    if (
      !sectionChanged &&
      row.order !== undefined &&
      existing.order !== undefined &&
      String(row.order) !== String(existing.order)
    ) {
      const sectionKey = idx.sectionKey
      const bucket = state.sectionRows.get(sectionKey)
      const positions = bucket
        ? [...bucket.keys()].sort((a, b) => a - b)
        : []
      const contiguous =
        positions.length > 0 &&
        positions.every((p, i) => i === 0 || p === positions[i - 1] + 1)
      if (contiguous && registry) {
        const sortFn = getRowSortFunction(
          registry,
          state.sortings ?? [],
          tableFields ?? fields,
          fields
        )
        commit('RESORT_SECTION_BUCKET', { sectionKey, sortFn })
      } else {
        commit('CLEAR_SECTION_TRACKING', sectionKey)
        await dispatch('ensureRowsForViewport')
      }
    }
  },

  /**
   * Realtime event: a row was created server-side. Bumps the target
   * section's tree count and, if the section is partially loaded,
   * inserts the row at the indicated position.
   */
  handleRealtimeRowCreated(
    { state, commit, rootGetters },
    { row, sectionPosition = null }
  ) {
    const fields = state.groupByFields
    const registry = state.registry
    if (!registry || fields.length === 0) return
    const leaf = leafPathForRow(row, fields, registry)
    ensureTreeNodesForPath(state, commit, leaf, fields)
    adjustAncestorCounts(commit, leaf, fields, +1)
    const sectionKey = pathKey(leaf, fields)
    // If we have any data for this section, insert at the BE-supplied
    // position so fetched ranges stay accurate (shift +1).
    if (sectionPosition !== null && state.sectionRows.has(sectionKey)) {
      commit('INSERT_ROW_INTO_SECTION', {
        sectionKey,
        position: sectionPosition,
        row,
      })
      // Apply search highlights to the inserted row.
      if (state.activeSearchTerm) {
        const inserted = state.sectionRows
          .get(sectionKey)
          ?.get(sectionPosition)
        if (inserted?._) {
          const tableFields = rootGetters['field/getAll'] ?? []
          const { matchSearch, fieldSearchMatches } =
            calculateSingleRowSearchMatches(
              inserted,
              state.activeSearchTerm,
              state.hideRowsNotMatchingSearch,
              tableFields,
              registry,
              getDefaultSearchModeFromEnv(this.$config)
            )
          inserted._.matchSearch = matchSearch
          inserted._.fieldSearchMatches = [...fieldSearchMatches]
        }
      }
    }
  },

  /**
   * Delete a row optimistically — pulls the row from its section
   * bucket + drops tree counts immediately, hits the BE, and rolls
   * back (re-inserts) on failure. Routes through the shared
   * `deleteRowOptimistically` helper so the eventual flat-grid
   * migration in PR 2 will go through the same code path.
   */
  async deleteRow({ state, commit }, { table, row }) {
    if (!row?.id) return
    const idx = state.rowIndex.get(row.id)
    if (!idx) return
    const sectionKey = idx.sectionKey
    const position = idx.position
    const fields = state.groupByFields
    const registry = state.registry
    const leafPath =
      registry && fields.length > 0
        ? leafPathForRow(row, fields, registry)
        : null

    // Tree counts go down first so the layout closes the row's
    // slot at the same time the row leaves the bucket. Reverse on
    // BE failure via the adapter's `insert` callback.
    if (leafPath) adjustAncestorCounts(commit, leafPath, fields, -1)

    return deleteRowOptimistically({
      client: this.$client,
      table,
      row,
      remove: () =>
        commit('REMOVE_ROW_FROM_SECTION', {
          sectionKey,
          position,
        }),
      insert: (rolledBack) => {
        // Rollback: put the row back where it was and restore tree
        // counts. The bucket may have shifted in the interim — we
        // insert at the original position; `INSERT_ROW_INTO_SECTION`
        // shifts later positions up to make room.
        commit('INSERT_ROW_INTO_SECTION', {
          sectionKey,
          position,
          row: rolledBack,
        })
        if (leafPath) adjustAncestorCounts(commit, leafPath, fields, +1)
      },
    })
  },

  /**
   * Inline cell edit pipeline: compute the new/old/request payloads,
   * dispatch `optimisticEditRow` (which handles tree counts + the
   * structural move when a group-by field changes), then PATCH the
   * BE. On success, `commitPendingEdit` writes the BE response in
   * place + clears pending. On failure, `rollbackPendingEdit`
   * reverses the optimistic effect.
   *
   * Caller (the GridView container) supplies `table`, `view`, `row`,
   * `field`, `value`, `oldValue` — exactly the shape the flat grid's
   * `GridViewCell` emits via `@update`.
   */
  async updateRowValue(
    { state, commit, dispatch },
    { table, view, fields, row, field, value, oldValue }
  ) {
    const registry = state.registry ?? this.$registry
    const { newRowValues, oldRowValues, updateRequestValues } =
      prepareNewOldAndUpdateRequestValues(
        row,
        fields,
        field,
        value,
        oldValue,
        registry
      )
    const rowId = row.id

    // 1. Optimistic: write the patch (and move sections if a group-by
    //    value changed). Passing `fields` lets optimisticEditRow find
    //    the new row's sorted insertion position in the target
    //    section using the same sort function the BE applies.
    await dispatch('optimisticEditRow', {
      rowId,
      values: newRowValues,
      fields,
    })

    // 2. Persist.
    try {
      const response = await RowService(this.$client).batchUpdate(
        table.id,
        [updateRequestValues],
        null,
        view.id
      )
      const items = response?.data?.items ?? []
      const beRow = items.find((r) => r.id === rowId) ?? items[0] ?? null
      await dispatch('commitPendingEdit', { rowId, beRow })

      // Client-side re-evaluation: does the row still match
      // filters? Is it still at its sorted index? Drives the "row
      // has moved" / "row doesn't match filters" warning until the
      // user unselects. Goes through the shared `reapplyMatchFlags`
      // so this matches whatever the flat grid does post-update.
      if (beRow) {
        const idx = state.rowIndex.get(rowId)
        const bucket = idx ? state.sectionRows.get(idx.sectionKey) : null
        const updatedRow = bucket?.get(idx.position)
        if (updatedRow) {
          reapplyMatchFlags({
            registry,
            row: updatedRow,
            view,
            fields,
            groupBys: state.groupByFields,
            rowsForMatchCheck: () =>
              bucket
                ? [...bucket.entries()]
                    .sort(([a], [b]) => a - b)
                    .map(([, r]) => r)
                : [],
            applyMatchFlags: (id, flags) =>
              commit('SET_ROW_MATCH_FLAGS', { rowId: id, ...flags }),
          })
        }
      }
    } catch (error) {
      // Roll back the structural + patch overlay so the row reverts
      // to its pre-edit BE-truthful state. We pass `oldRowValues` to
      // optimisticEditRow inside the rollback only when the rollback
      // can't fully undo via the move (e.g., a pending merge state).
      await dispatch('rollbackPendingEdit', { rowId })
      throw error
    }
  },

  /**
   * Batched multi-cell update used by the paste-rectangle pipeline.
   * `updates` is `[{ row, fieldValuePairs: [{ field, value, oldValue }] }]`
   * — one entry per affected row, with every cell change for that row.
   *
   * Applies the per-row patch optimistically (so all rectangle cells
   * appear updated at once), then makes a single BE `batchUpdate`
   * round-trip and commits / re-evaluates match flags per row. On
   * failure every optimistic edit is rolled back.
   */
  async batchUpdateRowValues(
    { state, commit, dispatch },
    { table, view, fields, updates }
  ) {
    if (!updates?.length) return
    const registry = state.registry ?? this.$registry
    const optimisticallyApplied = []
    const requests = []
    for (const { row, fieldValuePairs } of updates) {
      if (!row || !fieldValuePairs?.length) continue
      const { newRowValues, updateRequestValues } = prepareRowMultiFieldUpdate(
        row,
        fields,
        fieldValuePairs,
        registry
      )
      await dispatch('optimisticEditRow', {
        rowId: row.id,
        values: newRowValues,
        fields,
      })
      optimisticallyApplied.push(row.id)
      requests.push(updateRequestValues)
    }
    if (!requests.length) return
    try {
      const response = await RowService(this.$client).batchUpdate(
        table.id,
        requests,
        null,
        view.id
      )
      const items = response?.data?.items ?? []
      for (const rowId of optimisticallyApplied) {
        const beRow = items.find((r) => r.id === rowId) ?? null
        await dispatch('commitPendingEdit', { rowId, beRow })
        if (!beRow) continue
        const idx = state.rowIndex.get(rowId)
        const bucket = idx ? state.sectionRows.get(idx.sectionKey) : null
        const updatedRow = bucket?.get(idx.position)
        if (!updatedRow) continue
        reapplyMatchFlags({
          registry,
          row: updatedRow,
          view,
          fields,
          groupBys: state.groupByFields,
          rowsForMatchCheck: () =>
            bucket
              ? [...bucket.entries()]
                  .sort(([a], [b]) => a - b)
                  .map(([, r]) => r)
              : [],
          applyMatchFlags: (id, flags) =>
            commit('SET_ROW_MATCH_FLAGS', { rowId: id, ...flags }),
        })
      }
    } catch (error) {
      for (const rowId of optimisticallyApplied) {
        await dispatch('rollbackPendingEdit', { rowId })
      }
      throw error
    }
  },

  /**
   * Drop a row into a different section: patches the row's group-by
   * field values to match `targetPath`. The existing optimistic-edit
   * pipeline (`updateRowValue` via `batchUpdateRowValues`) handles
   * the structural section move + BE persist + match-flag refresh.
   * Read-only group-by fields are skipped (BE rejects them on
   * update); if every group-by field is read-only the drop is
   * silently dropped.
   */
  async moveRowToSection(
    { state, dispatch },
    { table, view, fields: allFields, row, targetPath }
  ) {
    const registry = state.registry ?? this.$registry
    const groupFields = state.groupByFields
    if (!registry || !groupFields?.length || !row) return
    const fieldValuePairs = []
    for (const f of groupFields) {
      const fieldKey = `field_${f.id}`
      if (!(fieldKey in targetPath)) continue
      const fieldType = registry.get('field', f.type)
      if (fieldType.isReadOnlyField?.(f)) continue
      const newValue = fieldType.getRowValueFromGroupValue(
        f,
        targetPath[fieldKey]
      )
      if (newValue === row[fieldKey]) continue
      fieldValuePairs.push({
        field: f,
        value: newValue,
        oldValue: row[fieldKey],
      })
    }
    if (!fieldValuePairs.length) return
    await dispatch('batchUpdateRowValues', {
      table,
      view,
      fields: allFields,
      updates: [{ row, fieldValuePairs }],
    })
  },

  /**
   * Drag-reorder a row within its own section. `beforeRowId` is the
   * id of the row that should end up immediately *below* the dragged
   * row after the move; `null` means "drop at the end of the section".
   * Cross-section drag is rejected: changing the row's group is a
   * separate edit and would require updating the group-by field
   * value, not just the row order.
   */
  async moveRow(
    { state, commit },
    { table, rowId, beforeRowId }
  ) {
    const sourceIdx = state.rowIndex.get(rowId)
    if (!sourceIdx) return
    const bucket = state.sectionRows.get(sourceIdx.sectionKey)
    if (!bucket) return

    let targetPosition
    if (beforeRowId == null) {
      const lastFilled = [...bucket.keys()].reduce(
        (max, k) => (k > max ? k : max),
        -1
      )
      targetPosition = lastFilled + 1
    } else {
      const beforeIdx = state.rowIndex.get(beforeRowId)
      if (!beforeIdx || beforeIdx.sectionKey !== sourceIdx.sectionKey) return
      targetPosition = beforeIdx.position
    }

    if (sourceIdx.position === targetPosition) return
    // If we're moving downward, removing the source shifts the
    // target down by 1 — adjust before the structural mutation.
    const adjustedTarget =
      targetPosition > sourceIdx.position
        ? targetPosition - 1
        : targetPosition

    const sourceRowSnapshot = { ...bucket.get(sourceIdx.position) }
    commit('MOVE_ROW_BETWEEN_SECTIONS', {
      rowId,
      fromSectionKey: sourceIdx.sectionKey,
      fromPosition: sourceIdx.position,
      toSectionKey: sourceIdx.sectionKey,
      toPosition: adjustedTarget,
    })

    try {
      const response = await RowService(this.$client).move(
        table.id,
        rowId,
        beforeRowId
      )
      const beRow = response?.data ?? null
      if (beRow) commit('UPDATE_ROW_DATA', { rowId, patch: beRow })
    } catch (error) {
      // Rollback: move back to the original position.
      const idx = state.rowIndex.get(rowId)
      if (idx) {
        commit('MOVE_ROW_BETWEEN_SECTIONS', {
          rowId,
          fromSectionKey: idx.sectionKey,
          fromPosition: idx.position,
          toSectionKey: sourceIdx.sectionKey,
          toPosition: sourceIdx.position,
        })
      }
      // Restore the original row data in case it was clobbered.
      const restored = state.sectionRows
        .get(sourceIdx.sectionKey)
        ?.get(sourceIdx.position)
      if (restored) {
        commit('UPDATE_ROW_DATA', { rowId, patch: sourceRowSnapshot })
      }
      throw error
    }
  },

  /**
   * Create a new row inside `groupPath` (the leaf path of the group
   * whose "+ Add row" affordance the user clicked).
   *
   * Delegates to the shared `createRowOptimistically` helper so the
   * flat grid and the grouped grid will run identical create flows
   * (defaults, optimistic insert with spinner, BE PATCH, match-flag
   * computation, rollback). The only grouped-specific work here is:
   *
   *   - Compute the supplied row-form values from `groupPath`,
   *     skipping read-only fields the BE rejects on create.
   *   - Adjust tree row-counts up so the layout opens a slot, and
   *     roll them back on BE failure.
   *   - Provide store adapters (`insert`, `replace`, `remove`,
   *     `applyMatchFlags`) that write into the per-section bucket.
   */
  async createRowInGroup(
    { state, commit },
    {
      table,
      view,
      fields: allFields,
      groupPath,
      // Optional params used by the row-context actions
      // (insertRowAboveRow, insertRowBelowRow, duplicateRow):
      beforeId = null,
      positionInSection = 'append',
      suppliedValuesOverride = null,
    }
  ) {
    const groupFields = state.groupByFields
    const registry = state.registry ?? this.$registry
    if (!registry || !groupFields?.length) return null

    let suppliedValues = {}
    for (const f of groupFields) {
      const key = `field_${f.id}`
      if (!(key in groupPath)) continue
      const fieldType = registry.get('field', f.type)
      if (fieldType.isReadOnlyField?.(f)) continue
      suppliedValues[key] = fieldType.getRowValueFromGroupValue(
        f,
        groupPath[key]
      )
    }
    if (suppliedValuesOverride) {
      suppliedValues = { ...suppliedValues, ...suppliedValuesOverride }
    }

    adjustAncestorCounts(commit, groupPath, groupFields, +1)
    const sectionKey = pathKey(groupPath, groupFields)
    const newSection = findSectionInLayout(state, sectionKey)
    const targetPosition =
      positionInSection === 'append'
        ? Math.max(0, (newSection?.rowCount ?? 1) - 1)
        : positionInSection

    try {
      return await createRowOptimistically({
        client: this.$client,
        registry,
        table,
        view,
        fields: allFields ?? [],
        suppliedValues,
        insert: (optimisticRow) =>
          commit('INSERT_ROW_INTO_SECTION', {
            sectionKey,
            position: targetPosition,
            row: optimisticRow,
          }),
        replace: (_tempId, beRow) =>
          commit('REPLACE_ROW_AT_POSITION', {
            sectionKey,
            position: targetPosition,
            newRow: beRow,
          }),
        remove: () => {
          commit('REMOVE_ROW_FROM_SECTION', {
            sectionKey,
            position: targetPosition,
          })
          adjustAncestorCounts(commit, groupPath, groupFields, -1)
        },
        applyMatchFlags: (rowId, flags) =>
          commit('SET_ROW_MATCH_FLAGS', { rowId, ...flags }),
        selectPrimaryCell: true,
        selectCell: (rowId, fieldId) =>
          commit('SELECT_CELL', { rowId, fieldId }),
        rowsForMatchCheck: () => {
          // Compare against the loaded rows of the row's section so
          // the helper can decide whether the optimistic position
          // matches the BE-truth sort order. Sparse buckets just
          // mean we're checking against a partial set — same trade
          // -off the flat grid makes when its buffer is partial.
          const bucket = state.sectionRows.get(sectionKey)
          if (!bucket) return []
          return [...bucket.entries()]
            .sort(([a], [b]) => a - b)
            .map(([, row]) => row)
        },
        groupBys: groupFields,
      })
    } catch (error) {
      // The helper's `remove` adapter already pulled the optimistic
      // row out and rolled tree counts back, so we just rethrow.
      throw error
    }
  },

  /**
   * Insert a row directly above `sourceRow` — new row inherits the
   * source's group-by values and goes at the same section position,
   * shifting the source down. Uses `createRowInGroup` so the
   * optimistic-create lifecycle stays one code path.
   */
  async insertRowAboveRow(
    { state, dispatch },
    { table, view, fields: allFields, sourceRow }
  ) {
    const groupFields = state.groupByFields
    const registry = state.registry ?? this.$registry
    if (!sourceRow?.id || !registry) return null
    const idx = state.rowIndex.get(sourceRow.id)
    const groupPath = leafPathForRow(sourceRow, groupFields, registry)
    return dispatch('createRowInGroup', {
      table,
      view,
      fields: allFields,
      groupPath,
      beforeId: sourceRow.id,
      positionInSection: idx ? idx.position : 'append',
    })
  },

  /**
   * Insert a row directly below `sourceRow` — new row inherits the
   * source's group-by values and sits at the next section position.
   * `beforeId` points at the BE-order successor of `sourceRow` (the
   * next row in the same section) so the BE places the row between
   * them.
   */
  async insertRowBelowRow(
    { state, dispatch },
    { table, view, fields: allFields, sourceRow }
  ) {
    const groupFields = state.groupByFields
    const registry = state.registry ?? this.$registry
    if (!sourceRow?.id || !registry) return null
    const idx = state.rowIndex.get(sourceRow.id)
    const nextRow = findNextRowInSection(state, sourceRow.id)
    const groupPath = leafPathForRow(sourceRow, groupFields, registry)
    return dispatch('createRowInGroup', {
      table,
      view,
      fields: allFields,
      groupPath,
      beforeId: nextRow?.id ?? null,
      positionInSection: idx ? idx.position + 1 : 'append',
    })
  },

  /**
   * Duplicate `sourceRow` — copies all non-read-only field values
   * (passed through each field type's `prepareValueForDuplicate` to
   * strip values that shouldn't carry over, e.g. autonumber) and
   * inserts directly below the source.
   */
  async duplicateRow(
    { state, dispatch },
    { table, view, fields: allFields, sourceRow }
  ) {
    const groupFields = state.groupByFields
    const registry = state.registry ?? this.$registry
    if (!sourceRow?.id || !registry) return null
    const idx = state.rowIndex.get(sourceRow.id)
    const nextRow = findNextRowInSection(state, sourceRow.id)
    const groupPath = leafPathForRow(sourceRow, groupFields, registry)
    const suppliedValuesOverride = buildDuplicateValuesFromRow(
      sourceRow,
      allFields ?? [],
      registry
    )
    return dispatch('createRowInGroup', {
      table,
      view,
      fields: allFields,
      groupPath,
      beforeId: nextRow?.id ?? null,
      positionInSection: idx ? idx.position + 1 : 'append',
      suppliedValuesOverride,
    })
  },

  /**
   * Realtime event: a row was deleted server-side. Structural remove
   * + tree count -1.
   */
  handleRealtimeRowDeleted({ state, commit }, { rowId }) {
    const idx = state.rowIndex.get(rowId)
    const fields = state.groupByFields
    const registry = state.registry
    if (!idx) return
    if (registry && fields.length > 0) {
      const bucket = state.sectionRows.get(idx.sectionKey)
      const row = bucket?.get(idx.position)
      if (row) {
        const leaf = leafPathForRow(row, fields, registry)
        adjustAncestorCounts(commit, leaf, fields, -1)
      }
    }
    commit('REMOVE_ROW_FROM_SECTION', {
      sectionKey: idx.sectionKey,
      position: idx.position,
    })
  },
}

export const getters = {
  tree: (s) => s.tree,
  collapse: (s) => s.collapse,
  sectionRows: (s) => s.sectionRows,
  rowIndex: (s) => s.rowIndex,
  pendingMutations: (s) => s.pendingMutations,
  viewport: (s) => s.viewport,
  groupByFields: (s) => s.groupByFields,
  sortings: (s) => s.sortings,
  selectedCell: (s) => s.selectedCell,
  layout: (s) =>
    buildLayout({
      nodes: s.tree.nodes,
      collapse: s.collapse,
      fields: s.groupByFields,
      rowHeight: s.rowHeight,
    }),
  rowHeight: (s) => s.rowHeight,
  // Linearise visible rows into a single integer index — slot by
  // slot, section by section, in layout order. Used by the
  // multi-cell rectangle selection: it lets the flat grid's
  // existing `[min, max]` row-index state work unchanged for
  // grouped, since both grids now agree on what "row index" means
  // for selection.
  linearisedRowSlots: (s, getters) => {
    const slots = []
    const fields = s.groupByFields
    const layout = getters.layout
    for (const item of layout.items) {
      if (item.type !== 'rowSection') continue
      const sectionKey = pathKey(item.path, fields)
      const bucket = s.sectionRows.get(sectionKey)
      for (let i = 0; i < item.rowCount; i++) {
        slots.push({
          sectionKey,
          position: i,
          rowId: bucket?.get(i)?.id ?? null,
        })
      }
    }
    return slots
  },
  linearisedRowIndexById: (s, getters) => (rowId) => {
    const slots = getters.linearisedRowSlots
    for (let i = 0; i < slots.length; i++) {
      if (slots[i].rowId === rowId) return i
    }
    return -1
  },
  // Sum of leaf rowCounts across the whole tree, regardless of which
  // groups are currently collapsed. Used by the footer's "N rows"
  // label, which should report the full table size, not only the
  // currently-visible portion.
  totalRowCount: (s) => {
    const maxDepth = (s.groupByFields?.length ?? 0) - 1
    if (maxDepth < 0) return 0
    let total = 0
    for (const node of s.tree.nodes) {
      if (node.depth !== maxDepth) continue
      total += node.rowCount ?? node.row_count ?? 0
    }
    return total
  },
}

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
}
