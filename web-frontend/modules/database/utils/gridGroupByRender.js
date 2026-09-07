export const HEADER_HEIGHT = 48
export const ROW_HEIGHT = 33
export const GROUP_GAP = 8
// The add-row slot keeps the small row height even when the view uses taller rows,
// matching the fixed-height ungrouped `GridViewRowAdd`.
export const ADD_ROW_HEIGHT = ROW_HEIGHT

export const GROUP_BY_LAYOUT_BANNER = 'banner'
export const GROUP_BY_LAYOUT_COLUMN = 'column'

const BANNER_GEOMETRY = Object.freeze({
  layout: GROUP_BY_LAYOUT_BANNER,
  headerHeight: HEADER_HEIGHT,
  groupGap: GROUP_GAP,
  addRowHeight: ADD_ROW_HEIGHT,
  addRowPerGroup: true,
  unloadedGroupHeight: HEADER_HEIGHT,
})

const EXPAND_ALL = Object.freeze({ mode: 'expand', paths: [] })

export function getLayoutGeometry(layout, rowHeight = ROW_HEIGHT) {
  if (layout !== GROUP_BY_LAYOUT_COLUMN) {
    return BANNER_GEOMETRY
  }
  return {
    layout: GROUP_BY_LAYOUT_COLUMN,
    headerHeight: 0,
    groupGap: 0,
    addRowHeight: ADD_ROW_HEIGHT,
    addRowPerGroup: false,
    // A row per unloaded group keeps the placeholder tall enough to reach the viewport.
    unloadedGroupHeight: rowHeight,
  }
}

function layoutGeometryOf(layout) {
  return layout?.geometry || BANNER_GEOMETRY
}

function pushGroupHeader(items, geometry, rowHeight, node) {
  if (geometry.headerHeight === 0) {
    items.push({
      type: 'groupSpan',
      depth: node.depth,
      path: node.path,
      display: node.display,
      rowCount: node.rowCount,
      y: node.y,
      height: node.rowCount * rowHeight,
    })
    return node.y
  }
  items.push({
    type: 'header',
    depth: node.depth,
    path: node.path,
    display: node.display,
    rowCount: node.rowCount,
    aggregationRowCount: node.aggregationRowCount,
    y: node.y,
    height: geometry.headerHeight,
    collapsed: node.collapsed,
    gapAbove: node.gapAbove,
    aggregations: node.aggregations,
  })
  return node.y + geometry.headerHeight
}

function pushGroupAddRow(items, geometry, node) {
  if (!geometry.addRowPerGroup) {
    return node.y
  }
  items.push({
    type: 'addRow',
    depth: node.depth,
    path: node.path,
    display: node.display,
    rowCount: node.rowCount,
    y: node.y,
    height: geometry.addRowHeight,
  })
  return node.y + geometry.addRowHeight
}

function pushTrailingAddRow(items, geometry, y, rootPageLoaded) {
  // Without per-group add-row lines the grid must always end with one.
  const needed = geometry.addRowPerGroup
    ? rootPageLoaded && items.length === 0
    : rootPageLoaded || items.length > 0
  if (!needed) {
    return y
  }
  items.push({
    type: 'addRow',
    depth: 0,
    path: {},
    y,
    height: geometry.addRowHeight,
  })
  return y + geometry.addRowHeight
}

const GROUP_BANNER_DEPTH_INDENT_PX = 24
const GROUP_BANNER_BASE_GUTTER = 12
const GROUP_BANNER_CHEVRON_WIDTH = 24
// Caps how far the deepest chevron indents. Beyond this the per-level step shrinks
// instead of pushing the chevron (and the field name + count after it) off the right,
// keeping that column aligned within the row-details lane at every depth.
const GROUP_BANNER_MAX_INDENT_PX = 50

/**
 * The left indent (px) of a group banner's chevron at `depth`, shared by the rendered
 * banner and its loading skeleton so they line up. The per-level step shrinks as the
 * number of group-by levels grows and is capped so the chevron stays inside the
 * `rowDetailsWidth` lane.
 */
export function groupBannerIndentPx(depth, levelCount, rowDetailsWidth) {
  const maxDepth = Math.max(levelCount - 1, 0)
  if (maxDepth <= 0) {
    return GROUP_BANNER_BASE_GUTTER
  }
  const maxShift = Math.min(
    GROUP_BANNER_MAX_INDENT_PX,
    Math.max(
      0,
      rowDetailsWidth - GROUP_BANNER_BASE_GUTTER - GROUP_BANNER_CHEVRON_WIDTH
    )
  )
  const step = Math.min(GROUP_BANNER_DEPTH_INDENT_PX, maxShift / maxDepth)
  return GROUP_BANNER_BASE_GUTTER + depth * step
}
// Fallback sibling-group page size for callers/tests that don't pass `pageSize`. In
// production the store passes its row `bufferRequestSize`; keep both aligned with the
// server's GROUP_BY_DATA_DEFAULT_LIMIT so a viewport fetches comparable groups and rows.
const GROUP_PAGE_SIZE = 40

const PATH_KEY_SEP = '\x1f'

export function pathKey(path, fields) {
  const parts = []
  for (const field of fields) {
    const key = `field_${field.id}`
    if (!(key in path)) {
      break
    }
    // Numeric-sort m2m id arrays so a group is keyed by its set of ids, not their order,
    // regardless of how the source (server- or row-derived) ordered them.
    const value = path[key]
    const canonical = Array.isArray(value)
      ? [...value].sort((a, b) => a - b)
      : value
    parts.push(`${key}:${JSON.stringify(canonical)}`)
  }
  return parts.join(PATH_KEY_SEP)
}

/**
 * Builds the set of pathKeys for the collapse exception list. Collapse-all mode
 * needs every prefix so expanded descendants can make their ancestors visible.
 * Expand-all mode must only match exact paths, otherwise collapsing a child also
 * collapses its parent.
 */
function collapseExceptionKeys(collapseState, fields) {
  const keys = new Set()
  for (const path of collapseState.paths || []) {
    let pathDepth = 0
    for (const field of fields) {
      if (!(`field_${field.id}` in path)) {
        break
      }
      pathDepth += 1
    }

    if (pathDepth === 0) {
      continue
    }

    if (collapseState.mode === 'collapse') {
      for (let depth = 1; depth <= pathDepth; depth++) {
        keys.add(pathKey(path, fields.slice(0, depth)))
      }
    } else {
      keys.add(pathKey(path, fields.slice(0, pathDepth)))
    }
  }
  return keys
}

function pathCollapsedAgainst(path, mode, exceptionKeys, fields) {
  // pathKey self-trims at the path's own depth, so this is the node's depth-key.
  const inList = exceptionKeys.has(pathKey(path, fields))
  return mode === 'collapse' ? !inList : inList
}

export function buildLayout({
  nodes,
  pages = null,
  collapse,
  fields,
  rowHeight = ROW_HEIGHT,
  pageSize = GROUP_PAGE_SIZE,
  layout = GROUP_BY_LAYOUT_BANNER,
  rootRowCount = null,
}) {
  const geometry = getLayoutGeometry(layout, rowHeight)
  const effectiveCollapse =
    geometry.layout === GROUP_BY_LAYOUT_COLUMN ? EXPAND_ALL : collapse

  if (pages !== null) {
    return buildPagedLayout({
      pages,
      collapse: effectiveCollapse,
      fields,
      rowHeight,
      pageSize,
      geometry,
      rootRowCount,
    })
  }

  const items = []
  let y = 0
  let visibleRowCount = 0

  if (!nodes || nodes.length === 0 || !fields || fields.length === 0) {
    return { items, totalHeight: 0, totalRowCount: 0, geometry }
  }

  const maxDepth = fields.length - 1
  const exceptionKeys = collapseExceptionKeys(effectiveCollapse, fields)
  let skipDescendantsAtDepth = -1
  let lastPlacedDepth = null

  for (const node of nodes) {
    if (skipDescendantsAtDepth >= 0 && node.depth > skipDescendantsAtDepth) {
      continue
    }
    skipDescendantsAtDepth = -1

    // Hide optimistically-emptied groups at any depth (the node is kept for
    // reconciliation); an emptied parent hides its whole subtree.
    if ((node.rowCount ?? node.row_count ?? 0) === 0) {
      skipDescendantsAtDepth = node.depth
      continue
    }

    // A gap separates sibling groups at every depth; only a group directly under
    // its parent's banner (a first child) sits flush against it.
    const gapAbove = lastPlacedDepth !== null && lastPlacedDepth >= node.depth
    if (gapAbove) {
      y += geometry.groupGap
    }
    lastPlacedDepth = node.depth

    const collapsed = pathCollapsedAgainst(
      node.path,
      effectiveCollapse.mode,
      exceptionKeys,
      fields
    )
    const rowCount = node.rowCount ?? node.row_count ?? 0
    const aggregationRowCount =
      node.aggregationRowCount ?? node.aggregation_row_count ?? rowCount

    y = pushGroupHeader(items, geometry, rowHeight, {
      depth: node.depth,
      path: node.path,
      display: node.display,
      rowCount,
      aggregationRowCount,
      y,
      collapsed,
      gapAbove,
      aggregations: node.aggregations ?? null,
    })

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
        display: node.display,
        rowCount,
        y,
        height: sectionHeight,
        firstGlobalRowOffset: visibleRowCount,
        absoluteRowOffset: node.row_offset ?? visibleRowCount,
      })
      y += sectionHeight
      visibleRowCount += rowCount
      y = pushGroupAddRow(items, geometry, {
        depth: node.depth,
        path: node.path,
        display: node.display,
        rowCount,
        y,
      })
    }
  }

  y = pushTrailingAddRow(items, geometry, y, true)

  return { items, totalHeight: y, totalRowCount: visibleRowCount, geometry }
}

function getPage(pages, parentPath, fields) {
  return pages?.[pathKey(parentPath, fields)] || null
}

function getSortedLoadedIndexes(page) {
  return Object.keys(page?.nodes || {})
    .map((index) => Number(index))
    .sort((a, b) => a - b)
}

function unloadedGroupRangeHeight(
  startIndex,
  endIndex,
  geometry,
  rowSlotCount = null
) {
  const count = Math.max(0, endIndex - startIndex)
  if (count === 0) {
    return 0
  }
  if (geometry.layout === GROUP_BY_LAYOUT_COLUMN && rowSlotCount !== null) {
    return Math.max(0, rowSlotCount) * geometry.unloadedGroupHeight
  }
  const gaps = count - (startIndex === 0 ? 1 : 0)
  return count * geometry.unloadedGroupHeight + gaps * geometry.groupGap
}

function placeholderStartIndexAtOffset(item, offset, geometry) {
  const startIndex = item.siblingStartIndex
  const endIndex = item.siblingEndIndex
  const clampedOffset = Math.max(0, Math.min(offset, item.height))
  const slotHeight = geometry.unloadedGroupHeight
  const stride = slotHeight + geometry.groupGap

  if (startIndex === 0) {
    if (clampedOffset < slotHeight) {
      return startIndex
    }
    return Math.min(
      endIndex,
      startIndex + 1 + Math.floor((clampedOffset - slotHeight) / stride)
    )
  }

  return Math.min(endIndex, startIndex + Math.floor(clampedOffset / stride))
}

function pushUnloadedGroupPlaceholder({
  items,
  parentPath,
  depth,
  startIndex,
  endIndex,
  globalStartIndex,
  y,
  geometry,
  rowSlotCount = null,
}) {
  const height = unloadedGroupRangeHeight(
    startIndex,
    endIndex,
    geometry,
    rowSlotCount
  )
  if (height <= 0) {
    return y
  }
  items.push({
    type: 'groupPlaceholder',
    parentPath,
    depth,
    siblingStartIndex: startIndex,
    siblingEndIndex: endIndex,
    // Sibling index across all parents at this depth (the space the depth-page
    // offset lives in), which includes hidden emptied groups that emit no header.
    globalSiblingStartIndex: globalStartIndex,
    y,
    height,
  })
  return y + height
}

function buildPagedLayout({
  pages,
  collapse,
  fields,
  rowHeight = ROW_HEIGHT,
  pageSize = GROUP_PAGE_SIZE,
  geometry = BANNER_GEOMETRY,
  rootRowCount = null,
}) {
  const items = []
  let y = 0
  let visibleRowCount = 0

  if (!fields || fields.length === 0) {
    return { items, totalHeight: 0, totalRowCount: 0, geometry }
  }

  const maxDepth = fields.length - 1
  const exceptionKeys = collapseExceptionKeys(collapse, fields)

  // Breaks a self-referential descent: a stale page (e.g. built before a group-by field
  // was removed) can key to an ancestor already on the stack and recurse forever. Parent
  // paths are unique in a valid tree, so skipping a visited key only ever cuts a cycle.
  const visitedPageKeys = new Set()

  // Running count of siblings seen at each depth across all parents, in walk order (the
  // same order the server enumerates a depth). Includes hidden emptied groups, which emit
  // no header, so depth-page placeholders anchor to the offset the server actually uses.
  const globalSiblingCountByDepth = new Map()
  const globalSiblingCount = (d) => globalSiblingCountByDepth.get(d) || 0
  const advanceGlobalSiblingCount = (d, count) =>
    globalSiblingCountByDepth.set(d, globalSiblingCount(d) + count)

  const walkPage = (
    parentPath,
    depth,
    fallbackSiblingCount = 0,
    parentRowCount = null
  ) => {
    const pageCacheKey = pathKey(parentPath, fields)
    if (visitedPageKeys.has(pageCacheKey)) {
      return
    }
    visitedPageKeys.add(pageCacheKey)
    const page = getPage(pages, parentPath, fields)
    const totalSiblingCount =
      page?.totalSiblingCount ??
      page?.total_sibling_count ??
      fallbackSiblingCount
    const loadedIndexes = getSortedLoadedIndexes(page)
    const validLoadedIndexes = loadedIndexes.filter(
      (loadedIndex) => loadedIndex >= 0 && loadedIndex < totalSiblingCount
    )
    let remainingUnloadedSiblingCount = null
    let remainingUnloadedRowCount = null
    if (
      geometry.layout === GROUP_BY_LAYOUT_COLUMN &&
      Number.isFinite(parentRowCount)
    ) {
      const loadedRowCount = validLoadedIndexes.reduce((total, loadedIndex) => {
        const loadedNode = page?.nodes?.[loadedIndex]
        return total + (loadedNode?.rowCount ?? loadedNode?.row_count ?? 0)
      }, 0)
      remainingUnloadedSiblingCount = Math.max(
        0,
        totalSiblingCount - validLoadedIndexes.length
      )
      // Server groups are non-empty, so reserve at least one row for each sibling
      // when optimistic/stale counts momentarily disagree. Otherwise distribute the
      // parent's rows not accounted for by loaded siblings across the missing ranges.
      remainingUnloadedRowCount = Math.max(
        remainingUnloadedSiblingCount,
        parentRowCount - loadedRowCount
      )
    }

    const takeUnloadedRowSlots = (siblingCount) => {
      if (
        remainingUnloadedSiblingCount === null ||
        remainingUnloadedRowCount === null
      ) {
        return null
      }
      if (siblingCount >= remainingUnloadedSiblingCount) {
        const rowSlots = remainingUnloadedRowCount
        remainingUnloadedSiblingCount = 0
        remainingUnloadedRowCount = 0
        return rowSlots
      }

      const extraRows = Math.max(
        0,
        remainingUnloadedRowCount - remainingUnloadedSiblingCount
      )
      const rowSlots =
        siblingCount +
        Math.floor((extraRows * siblingCount) / remainingUnloadedSiblingCount)
      remainingUnloadedSiblingCount -= siblingCount
      remainingUnloadedRowCount -= rowSlots
      return rowSlots
    }
    let loadedPointer = 0
    let index = 0
    // Whether a sibling was already placed at this depth. Drives the depth-0 gap, which a
    // hidden (emptied) group must not trigger, so `index > 0` alone is not enough.
    let placedSibling = false

    while (index < totalSiblingCount) {
      const loadedIndex = loadedIndexes[loadedPointer]
      if (loadedIndex === undefined || loadedIndex > index) {
        const unloadedEnd = Math.min(
          loadedIndex === undefined ? totalSiblingCount : loadedIndex,
          Math.ceil((index + 1) / pageSize) * pageSize
        )
        const unloadedSiblingCount = unloadedEnd - index
        y = pushUnloadedGroupPlaceholder({
          items,
          parentPath,
          depth,
          startIndex: index,
          endIndex: unloadedEnd,
          globalStartIndex: globalSiblingCount(depth),
          y,
          geometry,
          rowSlotCount: takeUnloadedRowSlots(unloadedSiblingCount),
        })
        advanceGlobalSiblingCount(depth, unloadedSiblingCount)
        index = unloadedEnd
        placedSibling = true
        continue
      }

      if (loadedIndex < index) {
        loadedPointer += 1
        continue
      }

      const node = page.nodes[loadedIndex]
      // Hide optimistically-emptied groups at any depth (the node is kept for
      // reconciliation); an emptied parent hides its whole subtree by not walking
      // its child page. The slot still counts toward the depth offset, since the
      // server keeps enumerating the group until the move is persisted.
      if ((node.rowCount ?? node.row_count ?? 0) === 0) {
        advanceGlobalSiblingCount(depth, 1)
        index += 1
        loadedPointer += 1
        continue
      }
      const gapAbove = placedSibling
      if (gapAbove) {
        y += geometry.groupGap
      }
      placedSibling = true

      const collapsed = pathCollapsedAgainst(
        node.path,
        collapse.mode,
        exceptionKeys,
        fields
      )
      const rowCount = node.rowCount ?? node.row_count ?? 0
      const aggregationRowCount =
        node.aggregationRowCount ?? node.aggregation_row_count ?? rowCount
      const childrenCount = node.childrenCount ?? node.children_count ?? 0

      y = pushGroupHeader(items, geometry, rowHeight, {
        depth: node.depth ?? depth,
        path: node.path,
        display: node.display,
        rowCount,
        aggregationRowCount,
        y,
        collapsed,
        gapAbove,
        aggregations: node.aggregations ?? null,
      })

      if (!collapsed) {
        if ((node.depth ?? depth) === maxDepth) {
          const sectionHeight = rowCount * rowHeight
          const absoluteRowOffset = node.rowOffset ?? node.row_offset
          items.push({
            type: 'rowSection',
            depth: node.depth ?? depth,
            path: node.path,
            display: node.display,
            rowCount,
            y,
            height: sectionHeight,
            firstGlobalRowOffset:
              geometry.layout === GROUP_BY_LAYOUT_COLUMN &&
              absoluteRowOffset !== undefined &&
              absoluteRowOffset !== null
                ? absoluteRowOffset
                : visibleRowCount,
            absoluteRowOffset: absoluteRowOffset ?? 0,
          })
          y += sectionHeight
          visibleRowCount += rowCount
          y = pushGroupAddRow(items, geometry, {
            depth: node.depth ?? depth,
            path: node.path,
            display: node.display,
            rowCount,
            y,
          })
        } else {
          walkPage(
            node.path,
            (node.depth ?? depth) + 1,
            childrenCount,
            rowCount
          )
        }
      }

      advanceGlobalSiblingCount(node.depth ?? depth, 1)
      index += 1
      loadedPointer += 1
    }
  }

  walkPage({}, 0, 0, rootRowCount)

  const rootPageLoaded = getPage(pages, {}, fields) !== null
  y = pushTrailingAddRow(items, geometry, y, rootPageLoaded)

  return { items, totalHeight: y, totalRowCount: visibleRowCount, geometry }
}

/**
 * Returns the leaf row sections overlapping the viewport, each clipped to the on-screen
 * row range as {startPosition, endPosition} (positions within the section). Carries both
 * `firstGlobalRowOffset` (collapsed-layout space, drives the displayed row number) and
 * `absoluteRowOffset` (full grouped-row space, drives row fetching).
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
    if (item.type !== 'rowSection') {
      continue
    }
    const sectionTop = item.y
    const sectionBottom = item.y + item.height
    if (sectionBottom <= top) {
      continue
    }
    if (sectionTop >= bottom) {
      break
    }

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
    if (endPosition <= startPosition) {
      continue
    }
    ranges.push({
      sectionKey: pathKey(item.path, fields),
      sectionPath: item.path,
      firstGlobalRowOffset: item.firstGlobalRowOffset,
      absoluteRowOffset: item.absoluteRowOffset ?? item.firstGlobalRowOffset,
      rowCount: item.rowCount,
      startPosition,
      endPosition,
    })
  }

  return ranges
}

/**
 * Returns the {parentPath, offset, limit} group pages (page-boundary-aligned in
 * sibling-space) whose unloaded placeholder overlaps the viewport, so the store can
 * batch-fetch only the groups the user is about to see.
 */
export function visibleGroupPagesInViewport(
  layout,
  viewport,
  pageSize = GROUP_PAGE_SIZE
) {
  const top = viewport.scrollTop
  const bottom = viewport.scrollTop + viewport.clientHeight
  const pages = []

  for (const item of layout.items) {
    if (item.type !== 'groupPlaceholder') {
      continue
    }
    const itemBottom = item.y + item.height
    if (itemBottom <= top) {
      continue
    }
    if (item.y >= bottom) {
      break
    }

    pages.push({
      parentPath: item.parentPath,
      offset: Math.floor(item.siblingStartIndex / pageSize) * pageSize,
      limit: pageSize,
    })
  }

  return pages
}

/**
 * Depth-mode fast path: returns a single {depth, offset, limit} page spanning ALL
 * parents at the first depth whose unloaded placeholder overlaps the viewport. The
 * offset is in global sibling-space across that depth (not per-parent), so "expand/
 * collapse all" stays O(1) queries per viewport. Returns null when nothing is missing.
 */
export function visibleGroupDepthPageInViewport(
  layout,
  viewport,
  pageSize = GROUP_PAGE_SIZE
) {
  const top = viewport.scrollTop
  const bottom = viewport.scrollTop + viewport.clientHeight

  for (const item of layout.items) {
    if (item.type !== 'groupPlaceholder') {
      continue
    }

    const itemBottom = item.y + item.height
    if (itemBottom <= top) {
      continue
    }
    if (item.y >= bottom) {
      break
    }

    const visibleStart = placeholderStartIndexAtOffset(
      item,
      Math.max(top, item.y) - item.y,
      layoutGeometryOf(layout)
    )
    // globalSiblingStartIndex maps the placeholder's per-parent start into the
    // depth-wide sibling space the server offsets on, so batch-fetching the right page.
    const globalVisibleStart =
      item.globalSiblingStartIndex + (visibleStart - item.siblingStartIndex)
    const pageOffset = Math.floor(globalVisibleStart / pageSize) * pageSize

    return {
      depth: item.depth,
      offset: pageOffset,
      limit: pageSize,
    }
  }

  return null
}

/**
 * Clips the layout's ordered items to the viewport and, per visible row section, emits
 * only the on-screen row slots (`row` when loaded, `placeholder` otherwise). Collapsed
 * nodes contribute only their header. This is what the grid component renders.
 */
export function renderViewport({
  layout,
  sectionRows,
  viewport,
  fields,
  rowHeight = ROW_HEIGHT,
}) {
  const items = []
  const top = viewport.scrollTop
  const bottom = viewport.scrollTop + viewport.clientHeight
  const geometry = layoutGeometryOf(layout)

  for (const item of layout.items) {
    const itemBottom = item.y + item.height
    if (itemBottom <= top) {
      continue
    }
    if (item.y >= bottom) {
      break
    }

    if (item.type === 'groupSpan') {
      items.push({
        type: 'groupSpan',
        depth: item.depth,
        path: item.path,
        display: item.display,
        rowCount: item.rowCount,
        y: item.y,
        height: item.height,
      })
      continue
    }

    if (item.type === 'header') {
      items.push({
        type: 'header',
        depth: item.depth,
        path: item.path,
        display: item.display,
        rowCount: item.rowCount,
        aggregationRowCount: item.aggregationRowCount ?? item.rowCount,
        y: item.y,
        height: item.height,
        collapsed: item.collapsed,
        gapAbove: item.gapAbove,
        aggregations: item.aggregations ?? null,
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

    if (item.type === 'groupPlaceholder') {
      const rangeBottom = item.y + item.height
      if (geometry.headerHeight === 0) {
        const visibleTop = Math.max(top, item.y)
        items.push({
          type: 'groupRangePlaceholder',
          depth: item.depth,
          y: visibleTop,
          height: Math.min(bottom, rangeBottom) - visibleTop,
        })
        continue
      }
      // Fill the unloaded region with a staircase of skeleton headers, one per level the
      // group still nests through (the level count is known before the data loads), so
      // the structure shows instead of blank space while the descendant request resolves.
      const maxDepth = Math.max((fields?.length ?? 1) - 1, item.depth)
      const levelsBelow = maxDepth - item.depth + 1
      // Sibling groups are laid out with a gap between them (see
      // `unloadedGroupRangeHeight`), so step by the same stride or the staircase
      // over-produces slots across the gapped range.
      const slotStep = geometry.unloadedGroupHeight + geometry.groupGap
      const firstSlotIndex = Math.max(0, Math.floor((top - item.y) / slotStep))
      let slotIndex = firstSlotIndex
      for (
        let slotY = item.y + firstSlotIndex * slotStep;
        slotY < rangeBottom && slotY < bottom;
        slotY += slotStep, slotIndex += 1
      ) {
        items.push({
          type: 'groupSkeleton',
          depth: item.depth + (slotIndex % levelsBelow),
          y: slotY,
          height: Math.min(geometry.unloadedGroupHeight, rangeBottom - slotY),
        })
      }
      continue
    }

    const sectionKey = pathKey(item.path, fields)
    const bucket = sectionRows?.get?.(sectionKey)
    const visibleStart = Math.max(
      0,
      Math.floor((Math.max(top, item.y) - item.y) / rowHeight)
    )
    const visibleEnd = Math.min(
      item.rowCount,
      Math.ceil((Math.min(bottom, item.y + item.height) - item.y) / rowHeight)
    )

    for (let i = visibleStart; i < visibleEnd; i++) {
      const slotY = item.y + i * rowHeight
      const row = bucket?.get(i)
      if (row !== undefined) {
        items.push({
          type: 'row',
          row,
          path: item.path,
          y: slotY,
          height: rowHeight,
          sectionKey,
          position: i,
          globalRowOffset: item.firstGlobalRowOffset + i,
          groupEnd:
            geometry.layout === GROUP_BY_LAYOUT_COLUMN &&
            i === item.rowCount - 1,
        })
      } else {
        items.push({
          type: 'placeholder',
          path: item.path,
          y: slotY,
          height: rowHeight,
          indexInSection: i,
          sectionKey,
          globalRowOffset: item.firstGlobalRowOffset + i,
        })
      }
    }
  }

  return items
}

/**
 * Resolves a pointer position in grouped layout-space to a visible row insertion
 * slot. Group headers, gaps, unloaded row slots, and collapsed groups are not valid
 * targets. The returned `before` row is null for the explicit end-of-group slot.
 */
export function resolveGroupByRowMoveTarget({
  layout,
  sectionRows,
  contentY,
  fields,
  sourcePath,
  allowCrossGroup,
  rowHeight = ROW_HEIGHT,
}) {
  if (!sourcePath) {
    return null
  }
  const sourceSectionKey = pathKey(sourcePath, fields)

  for (const item of layout.items) {
    if (item.type === 'groupSpan') {
      continue
    }
    if (contentY < item.y || contentY >= item.y + item.height) {
      continue
    }

    if (item.type !== 'rowSection' && item.type !== 'addRow') {
      return null
    }

    // A root add-row line in an empty grouped view has only a partial path and
    // therefore cannot identify a destination leaf group.
    const completePath = fields.every(
      (field) => `field_${field.id}` in item.path
    )
    if (!completePath) {
      return null
    }

    const sectionKey = pathKey(item.path, fields)
    if (!allowCrossGroup && sectionKey !== sourceSectionKey) {
      return null
    }

    const { rowCount } = item
    const rows = sectionRows.get(sectionKey)
    if (item.type === 'rowSection') {
      const hoveredPosition = Math.min(
        rowCount - 1,
        Math.floor((contentY - item.y) / rowHeight)
      )
      if (rows?.get(hoveredPosition) === undefined) {
        return null
      }
    }

    const position =
      item.type === 'addRow'
        ? rowCount
        : Math.max(
            0,
            Math.min(rowCount, Math.round((contentY - item.y) / rowHeight))
          )
    const before = position === rowCount ? null : rows?.get(position)

    // A sparse/unloaded row slot cannot provide the row id needed by the move API.
    if (position < rowCount && before === undefined) {
      return null
    }

    return {
      before,
      path: item.path,
      display: item.display ?? null,
      sectionKey,
      position,
      // The add-row line already sits at the end-of-group slot.
      y: item.type === 'addRow' ? item.y : item.y + position * rowHeight,
    }
  }

  return null
}
