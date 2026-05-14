/**
 * Pure render core for the grouped grid view.
 *
 * The whole grouped layout is a deterministic function of:
 *   - the group tree (nodes + row counts) returned by the BE
 *   - the local collapse state
 *   - the viewport (scrollTop + clientHeight)
 *   - per-section row buckets (Map<positionInSection, RowData>)
 *   - pending optimistic mutations (data patches only — structural
 *     moves are materialised directly into the per-section buckets)
 *
 * Keeping that derivation pure (no Vuex, no DOM, no async) means:
 *   - The bug class "buffer says row X is at slot 5, heightIndex says
 *     slot 5 is group A, but row X's data says group B" cannot exist —
 *     there is no positional buffer to drift out of sync. A row lives
 *     in section X at position N because the store placed it there;
 *     no derivation from collapse-aware global offsets is required.
 *   - Every visual edge case (collapse, partial cache, optimistic
 *     overlays moving a row to another section, viewport windowing) is
 *     a unit test on fixed inputs that runs in milliseconds, instead of
 *     a browser interaction in an e2e test.
 *
 * The Vuex layer (in `store/view/gridGrouped.js`) keeps the per-section
 * buckets in sync with BE state. The Vue component (in
 * `components/view/grid/GridGrouped.vue`) renders the items produced
 * here into DOM. Both layers stay thin because the hard part lives
 * here.
 */

export const HEADER_HEIGHT = 48
export const ROW_HEIGHT = 33
// Vertical gap inserted before every depth-0 banner except the first,
// so consecutive top-level groups read as visually separate blocks
// rather than running together like a flat list of rows. Mirrors the
// breathing room Airtable shows between groups.
export const GROUP_GAP = 8

// Separator that no JSON-encoded value contains, used to build path
// keys that compare reliably across path objects with different key
// insertion orders.
const PATH_KEY_SEP = '\x1f'

/**
 * Build a deterministic string key for a group path. Two path objects
 * with the same field values produce the same key regardless of the
 * order their keys were inserted in.
 *
 * Iteration follows the order of `fields`, stopping at the first field
 * that isn't present in `path` — so a depth-1 path `{field_1, field_2}`
 * and the depth-0 prefix `{field_1}` produce different keys.
 */
export function pathKey(path, fields) {
  const parts = []
  for (const f of fields) {
    const key = `field_${f.id}`
    if (!(key in path)) break
    parts.push(JSON.stringify(path[key]))
  }
  return parts.join(PATH_KEY_SEP)
}

/**
 * Whether the supplied path is currently collapsed.
 *
 * The collapse state has two modes:
 *   - 'expand'   → groups default expanded; `paths` lists collapsed ones
 *   - 'collapse' → groups default collapsed; `paths` lists expanded ones
 *
 * Path comparison goes through `pathKey`, which compares by serialised
 * field values at the path's depth.
 */
export function isPathCollapsed(path, collapseState, fields) {
  const { mode, paths } = collapseState
  const depth = fields.findIndex((f) => !(`field_${f.id}` in path))
  const fieldsForDepth = depth === -1 ? fields : fields.slice(0, depth)
  const target = pathKey(path, fieldsForDepth)
  const inList = paths.some((p) => pathKey(p, fieldsForDepth) === target)
  return mode === 'collapse' ? !inList : inList
}

/**
 * Walk a group tree and produce the pixel layout — a flat list of
 * `header` and `rowSection` items annotated with their y position and
 * height. Collapsed groups emit only the header; their descendants are
 * skipped entirely.
 *
 * Tree shape contract: `nodes` is the BE-supplied DFS pre-order list
 * where each child immediately follows its parent. `depth` is 0-based.
 * Leaf nodes are nodes whose depth equals `fields.length - 1`.
 *
 * The `firstGlobalRowOffset` annotation on each row section is the
 * cumulative count of visible (non-collapsed-ancestor) leaf rows that
 * precede it in tree order — i.e., the BE global offset at which this
 * section's position 0 lives. The store uses this to translate
 * (sectionKey, positionInSection) into a BE pagination offset.
 */
export function buildLayout({
  nodes,
  collapse,
  fields,
  rowHeight = ROW_HEIGHT,
}) {
  const items = []
  let y = 0
  let visibleRowCount = 0

  if (!nodes || nodes.length === 0 || !fields || fields.length === 0) {
    return { items, totalHeight: 0, totalRowCount: 0 }
  }

  const maxDepth = fields.length - 1
  // Once we hit a collapsed node, we skip every following node whose
  // depth is greater than the collapsed node's depth — those are its
  // descendants. The collapse "stack" only needs to track the shallowest
  // currently-collapsed depth; anything strictly deeper is a descendant.
  let skipDescendantsAtDepth = -1
  let seenFirstDepth0 = false

  for (const node of nodes) {
    if (skipDescendantsAtDepth >= 0 && node.depth > skipDescendantsAtDepth) {
      continue
    }
    skipDescendantsAtDepth = -1

    // Air-style breathing room between top-level groups.
    if (node.depth === 0 && seenFirstDepth0) {
      y += GROUP_GAP
    }
    if (node.depth === 0) seenFirstDepth0 = true

    const collapsed = isPathCollapsed(node.path, collapse, fields)
    const rowCount = node.rowCount ?? node.row_count ?? 0

    items.push({
      type: 'header',
      depth: node.depth,
      path: node.path,
      rowCount,
      y,
      height: HEADER_HEIGHT,
      collapsed,
    })
    y += HEADER_HEIGHT

    if (collapsed) {
      skipDescendantsAtDepth = node.depth
      continue
    }

    if (node.depth === maxDepth) {
      const sectionHeight = rowCount * rowHeight
      items.push({
        type: 'rowSection',
        depth: node.depth,
        path: node.path,
        rowCount,
        y,
        height: sectionHeight,
        firstGlobalRowOffset: visibleRowCount,
      })
      y += sectionHeight
      visibleRowCount += rowCount
      // "+ Add row" affordance at the bottom of every visible leaf
      // section. Emitted even when rowCount is 0 (empty group), so
      // the user can create the first row.
      items.push({
        type: 'addRow',
        depth: node.depth,
        path: node.path,
        y,
        height: rowHeight,
      })
      y += rowHeight
    }
  }

  return { items, totalHeight: y, totalRowCount: visibleRowCount }
}

/**
 * Convert a y-pixel inside the layout to a global row offset (the BE's
 * collapse-aware ordering — what `fetchRows` returns at `offset=N`).
 * Pixels above the first rowSection return 0; pixels below the last
 * one return `totalRowCount - 1`. Pixels inside a banner snap to the
 * nearest row in the same y-range.
 */
export function pixelToRowOffset(layout, y, rowHeight = ROW_HEIGHT) {
  const items = layout.items
  if (!items || items.length === 0) return 0
  let lastRowSection = null
  for (const item of items) {
    if (item.type !== 'rowSection') continue
    if (y < item.y) {
      if (lastRowSection) {
        return Math.max(
          0,
          lastRowSection.firstGlobalRowOffset + lastRowSection.rowCount - 1
        )
      }
      return 0
    }
    if (y < item.y + item.height) {
      const within = Math.floor((y - item.y) / rowHeight)
      return item.firstGlobalRowOffset + Math.min(item.rowCount - 1, within)
    }
    lastRowSection = item
  }
  if (lastRowSection) {
    return lastRowSection.firstGlobalRowOffset + lastRowSection.rowCount - 1
  }
  return 0
}

/**
 * Convert a viewport [top, bottom] pixel range to the inclusive row
 * offset range it covers in the BE's collapse-aware ordering. Kept for
 * tests + occasional debugging — the runtime path now uses
 * `visibleSectionsInViewport` to drive per-section fetches directly.
 */
export function pixelRangeToRowOffsetRange(layout, top, bottom) {
  if (!layout.totalRowCount) {
    return { startOffset: 0, endOffset: 0 }
  }
  const startOffset = pixelToRowOffset(layout, top)
  const endOffsetInclusive = pixelToRowOffset(
    layout,
    Math.max(top, bottom - 1)
  )
  return {
    startOffset: Math.max(0, Math.min(startOffset, layout.totalRowCount - 1)),
    endOffset: Math.min(layout.totalRowCount, endOffsetInclusive + 1),
  }
}

/**
 * For every row section that overlaps the supplied viewport, return
 * the section-local position range the viewport covers (clamped to
 * the section's row count). Used by the store's fetch coordinator to
 * dispatch one fetch per section per uncovered block — eliminates the
 * old "viewport overlaps two sections, but the offset range straddles
 * the boundary" arithmetic the global-offset coordinator had to do.
 *
 * Each entry carries `firstGlobalRowOffset` so the caller can map
 * section position → BE pagination offset without re-walking the
 * layout.
 */
export function visibleSectionsInViewport(
  layout,
  viewport,
  fields,
  rowHeight = ROW_HEIGHT
) {
  const top = viewport.scrollTop
  const bottom = viewport.scrollTop + viewport.clientHeight
  const ranges = []
  for (const item of layout.items) {
    if (item.type !== 'rowSection') continue
    const sectionTop = item.y
    const sectionBottom = item.y + item.height
    if (sectionBottom <= top) continue
    if (sectionTop >= bottom) break
    const overlapTop = Math.max(top, sectionTop)
    const overlapBottom = Math.min(bottom, sectionBottom)
    const startPosition = Math.max(
      0,
      Math.floor((overlapTop - sectionTop) / rowHeight)
    )
    const endPosition = Math.min(
      item.rowCount,
      Math.ceil((overlapBottom - sectionTop) / rowHeight)
    )
    if (endPosition <= startPosition) continue
    ranges.push({
      sectionKey: pathKey(item.path, fields),
      sectionPath: item.path,
      firstGlobalRowOffset: item.firstGlobalRowOffset,
      rowCount: item.rowCount,
      startPosition,
      endPosition,
    })
  }
  return ranges
}

/**
 * Apply a pending mutation's `patch` (field values only) on top of a
 * cached row. Pending structural moves are NOT applied here — by the
 * time the render core runs, the moved row is already structurally in
 * its target section. Returns `row` unchanged if no patch is pending.
 */
export function getEffectiveRow(row, pendingMutations) {
  if (!row) return row
  const pending = pendingMutations?.get?.(row.id)
  if (!pending || !pending.patch) return row
  return { ...row, ...pending.patch }
}

/**
 * Produce the ordered DOM-shape item list for the visible portion of
 * the layout. Items returned:
 *   - `{ type: 'header', depth, path, y, height, collapsed, rowCount }`
 *   - `{ type: 'row', row, path, y, height }`
 *   - `{ type: 'placeholder', path, y, height, indexInSection }`
 *
 * Inputs:
 *   - `layout`         : from `buildLayout`
 *   - `sectionRows`    : Map<sectionKey, Map<positionInSection, RowData>>.
 *                        Source of truth for which row lives where —
 *                        structural moves (optimistic / realtime /
 *                        commit) have already updated these buckets.
 *   - `pending`        : Map<rowId, {patch, ...}>. Field-level overlay
 *                        applied to row data via `getEffectiveRow`.
 *   - `viewport`       : { scrollTop, clientHeight }.
 *   - `fields`         : groupByFields, for `pathKey` lookup.
 *
 * The viewport is a half-open pixel range `[scrollTop, scrollTop +
 * clientHeight)`. Callers wanting prefetch padding should widen the
 * viewport bounds themselves — this function emits exactly what
 * overlaps the supplied range, nothing more.
 *
 * Placeholders are emitted for slots in a row section whose row isn't
 * in the bucket yet. They carry `indexInSection` so the caller can
 * trigger a fetch for the missing positions without re-deriving them.
 */
export function renderViewport({
  layout,
  sectionRows,
  pending,
  viewport,
  fields,
  rowHeight = ROW_HEIGHT,
}) {
  const items = []
  const top = viewport.scrollTop
  const bottom = viewport.scrollTop + viewport.clientHeight
  const pendingMap = pending ?? new Map()

  for (const item of layout.items) {
    const itemBottom = item.y + item.height
    if (itemBottom <= top) continue
    if (item.y >= bottom) break

    if (item.type === 'header') {
      items.push({
        type: 'header',
        depth: item.depth,
        path: item.path,
        rowCount: item.rowCount,
        y: item.y,
        height: item.height,
        collapsed: item.collapsed,
      })
      continue
    }

    if (item.type === 'addRow') {
      items.push({
        type: 'addRow',
        depth: item.depth,
        path: item.path,
        y: item.y,
        height: item.height,
      })
      continue
    }

    const bucket = sectionRows?.get?.(pathKey(item.path, fields))
    const rowCount = item.rowCount
    for (let i = 0; i < rowCount; i++) {
      const slotY = item.y + i * rowHeight
      const slotBottom = slotY + rowHeight
      if (slotBottom <= top) continue
      if (slotY >= bottom) break
      const row = bucket?.get(i)
      if (row !== undefined) {
        items.push({
          type: 'row',
          row: getEffectiveRow(row, pendingMap),
          path: item.path,
          y: slotY,
          height: rowHeight,
        })
      } else {
        items.push({
          type: 'placeholder',
          path: item.path,
          y: slotY,
          height: rowHeight,
          indexInSection: i,
        })
      }
    }
  }

  return items
}
