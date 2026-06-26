export const HEADER_HEIGHT = 48
export const ROW_HEIGHT = 33
export const GROUP_GAP = 8

const PATH_KEY_SEP = '\x1f'

export function pathKey(path, fields) {
  const parts = []
  for (const field of fields) {
    const key = `field_${field.id}`
    if (!(key in path)) {
      break
    }
    parts.push(JSON.stringify(path[key]))
  }
  return parts.join(PATH_KEY_SEP)
}

export function isPathCollapsed(path, collapseState, fields) {
  const { mode, paths } = collapseState
  const depth = fields.findIndex((field) => !(`field_${field.id}` in path))
  const fieldsForDepth = depth === -1 ? fields : fields.slice(0, depth)
  const target = pathKey(path, fieldsForDepth)
  const inList = paths.some((p) => pathKey(p, fieldsForDepth) === target)
  return mode === 'collapse' ? !inList : inList
}

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
  let skipDescendantsAtDepth = -1
  let seenFirstDepth0 = false

  for (const node of nodes) {
    if (skipDescendantsAtDepth >= 0 && node.depth > skipDescendantsAtDepth) {
      continue
    }
    skipDescendantsAtDepth = -1

    if (node.depth === 0 && seenFirstDepth0) {
      y += GROUP_GAP
    }
    if (node.depth === 0) {
      seenFirstDepth0 = true
    }

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

export function pixelToRowOffset(layout, y, rowHeight = ROW_HEIGHT) {
  const items = layout.items
  if (!items || items.length === 0) {
    return 0
  }

  let lastRowSection = null
  for (const item of items) {
    if (item.type !== 'rowSection') {
      continue
    }
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

export function pixelRangeToRowOffsetRange(layout, top, bottom) {
  if (!layout.totalRowCount) {
    return { startOffset: 0, endOffset: 0 }
  }
  const startOffset = pixelToRowOffset(layout, top)
  const endOffsetInclusive = pixelToRowOffset(layout, Math.max(top, bottom - 1))
  return {
    startOffset: Math.max(0, Math.min(startOffset, layout.totalRowCount - 1)),
    endOffset: Math.min(layout.totalRowCount, endOffsetInclusive + 1),
  }
}

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
      rowCount: item.rowCount,
      startPosition,
      endPosition,
    })
  }

  return ranges
}

export function getEffectiveRow(row, pendingMutations) {
  if (!row) {
    return row
  }
  const pending = pendingMutations?.get?.(row.id)
  if (!pending || !pending.patch) {
    return row
  }
  return { ...row, ...pending.patch }
}

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
          row: getEffectiveRow(row, pendingMap),
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
