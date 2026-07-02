export const HEADER_HEIGHT = 48
export const ROW_HEIGHT = 33
export const GROUP_GAP = 8

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
}) {
  if (pages !== null) {
    return buildPagedLayout({ pages, collapse, fields, rowHeight, pageSize })
  }

  const items = []
  let y = 0
  let visibleRowCount = 0

  if (!nodes || nodes.length === 0 || !fields || fields.length === 0) {
    return { items, totalHeight: 0, totalRowCount: 0 }
  }

  const maxDepth = fields.length - 1
  const exceptionKeys = collapseExceptionKeys(collapse, fields)
  let skipDescendantsAtDepth = -1
  let seenFirstDepth0 = false

  for (const node of nodes) {
    if (skipDescendantsAtDepth >= 0 && node.depth > skipDescendantsAtDepth) {
      continue
    }
    skipDescendantsAtDepth = -1

    // Hide optimistically-emptied leaf groups (the node is kept for reconciliation).
    if (
      node.depth === maxDepth &&
      (node.rowCount ?? node.row_count ?? 0) === 0
    ) {
      continue
    }

    // Only top-level sibling groups are separated by a gap; the first one sits
    // flush under the head. `gapAbove` also drives the banner's darker top border.
    const gapAbove = node.depth === 0 && seenFirstDepth0
    if (gapAbove) {
      y += GROUP_GAP
    }
    if (node.depth === 0) {
      seenFirstDepth0 = true
    }

    const collapsed = pathCollapsedAgainst(
      node.path,
      collapse.mode,
      exceptionKeys,
      fields
    )
    const rowCount = node.rowCount ?? node.row_count ?? 0

    items.push({
      type: 'header',
      depth: node.depth,
      path: node.path,
      display: node.display,
      rowCount,
      y,
      height: HEADER_HEIGHT,
      collapsed,
      gapAbove,
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
        absoluteRowOffset: node.row_offset ?? visibleRowCount,
      })
      y += sectionHeight
      visibleRowCount += rowCount
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

function getPage(pages, parentPath, fields) {
  return pages?.[pathKey(parentPath, fields)] || null
}

function getSortedLoadedIndexes(page) {
  return Object.keys(page?.nodes || {})
    .map((index) => Number(index))
    .sort((a, b) => a - b)
}

function unloadedGroupRangeHeight(startIndex, endIndex, depth) {
  const count = Math.max(0, endIndex - startIndex)
  if (count === 0) {
    return 0
  }
  if (depth !== 0) {
    return count * HEADER_HEIGHT
  }
  const gaps = count - (startIndex === 0 ? 1 : 0)
  return count * HEADER_HEIGHT + gaps * GROUP_GAP
}

function placeholderStartIndexAtOffset(item, offset) {
  const startIndex = item.siblingStartIndex
  const endIndex = item.siblingEndIndex
  const clampedOffset = Math.max(0, Math.min(offset, item.height))

  if (item.depth !== 0) {
    return Math.min(
      endIndex,
      startIndex + Math.floor(clampedOffset / HEADER_HEIGHT)
    )
  }

  if (startIndex === 0) {
    if (clampedOffset < HEADER_HEIGHT) {
      return startIndex
    }
    return Math.min(
      endIndex,
      startIndex +
        1 +
        Math.floor(
          (clampedOffset - HEADER_HEIGHT) / (HEADER_HEIGHT + GROUP_GAP)
        )
    )
  }

  return Math.min(
    endIndex,
    startIndex + Math.floor(clampedOffset / (HEADER_HEIGHT + GROUP_GAP))
  )
}

function pushUnloadedGroupPlaceholder({
  items,
  parentPath,
  depth,
  startIndex,
  endIndex,
  globalStartIndex,
  y,
}) {
  const height = unloadedGroupRangeHeight(startIndex, endIndex, depth)
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
}) {
  const items = []
  let y = 0
  let visibleRowCount = 0

  if (!fields || fields.length === 0) {
    return { items, totalHeight: 0, totalRowCount: 0 }
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

  const walkPage = (parentPath, depth, fallbackSiblingCount = 0) => {
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
        y = pushUnloadedGroupPlaceholder({
          items,
          parentPath,
          depth,
          startIndex: index,
          endIndex: unloadedEnd,
          globalStartIndex: globalSiblingCount(depth),
          y,
        })
        advanceGlobalSiblingCount(depth, unloadedEnd - index)
        index = unloadedEnd
        placedSibling = true
        continue
      }

      if (loadedIndex < index) {
        loadedPointer += 1
        continue
      }

      const node = page.nodes[loadedIndex]
      // Hide optimistically-emptied leaf groups (the node is kept for reconciliation).
      // The slot still counts toward the depth offset, since the server keeps enumerating
      // the group until the move is persisted.
      if (
        (node.depth ?? depth) === maxDepth &&
        (node.rowCount ?? node.row_count ?? 0) === 0
      ) {
        advanceGlobalSiblingCount(depth, 1)
        index += 1
        loadedPointer += 1
        continue
      }
      const gapAbove = depth === 0 && placedSibling
      if (gapAbove) {
        y += GROUP_GAP
      }
      placedSibling = true

      const collapsed = pathCollapsedAgainst(
        node.path,
        collapse.mode,
        exceptionKeys,
        fields
      )
      const rowCount = node.rowCount ?? node.row_count ?? 0
      const childrenCount = node.childrenCount ?? node.children_count ?? 0

      items.push({
        type: 'header',
        depth: node.depth ?? depth,
        path: node.path,
        display: node.display,
        rowCount,
        y,
        height: HEADER_HEIGHT,
        collapsed,
        gapAbove,
      })
      y += HEADER_HEIGHT

      if (!collapsed) {
        if ((node.depth ?? depth) === maxDepth) {
          const sectionHeight = rowCount * rowHeight
          items.push({
            type: 'rowSection',
            depth: node.depth ?? depth,
            path: node.path,
            rowCount,
            y,
            height: sectionHeight,
            firstGlobalRowOffset: visibleRowCount,
            absoluteRowOffset: node.rowOffset ?? node.row_offset ?? 0,
          })
          y += sectionHeight
          visibleRowCount += rowCount
          items.push({
            type: 'addRow',
            depth: node.depth ?? depth,
            path: node.path,
            y,
            height: rowHeight,
          })
          y += rowHeight
        } else {
          walkPage(node.path, (node.depth ?? depth) + 1, childrenCount)
        }
      }

      advanceGlobalSiblingCount(node.depth ?? depth, 1)
      index += 1
      loadedPointer += 1
    }
  }

  walkPage({}, 0)

  return { items, totalHeight: y, totalRowCount: visibleRowCount }
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
      Math.max(top, item.y) - item.y
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

  for (const item of layout.items) {
    const itemBottom = item.y + item.height
    if (itemBottom <= top) {
      continue
    }
    if (item.y >= bottom) {
      break
    }

    if (item.type === 'header') {
      items.push({
        type: 'header',
        depth: item.depth,
        path: item.path,
        display: item.display,
        rowCount: item.rowCount,
        y: item.y,
        height: item.height,
        collapsed: item.collapsed,
        gapAbove: item.gapAbove,
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
      // Fill the unloaded region with a staircase of skeleton headers, one per level the
      // group still nests through (the level count is known before the data loads), so
      // the structure shows instead of blank space while the descendant request resolves.
      const rangeBottom = item.y + item.height
      const maxDepth = Math.max((fields?.length ?? 1) - 1, item.depth)
      const levelsBelow = maxDepth - item.depth + 1
      // Top-level groups are laid out with a gap between siblings (see
      // `unloadedGroupRangeHeight`), so step by the same stride or the staircase
      // over-produces slots across the gapped range.
      const slotStep =
        item.depth === 0 ? HEADER_HEIGHT + GROUP_GAP : HEADER_HEIGHT
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
          height: Math.min(HEADER_HEIGHT, rangeBottom - slotY),
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
