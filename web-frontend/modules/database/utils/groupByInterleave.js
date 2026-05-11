import { fieldValuesAreEqualInObjects } from '@baserow/modules/database/utils/groupBy'

const HEADER_HEIGHT = 48
const ROW_HEIGHT = 33

export const COLLAPSED_GROUPS_MODE_EXPAND = 'expand'
export const COLLAPSED_GROUPS_MODE_COLLAPSE = 'collapse'

/**
 * Returns the virtual y-coordinate where the depth-0 group identified by
 * `groupValues` starts (i.e. the top of its header), and the count of rows in
 * that group. Returns null if the group isn't present in the metadata — that
 * happens when the buffer hasn't covered it yet, in which case the caller
 * should leave the scroll position alone.
 */
export function findDepth0GroupPosition({
  groupValues,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
}) {
  if (fields.length === 0) return null
  const fieldsAtDepth = fields.slice(0, 1)
  const fieldKey = `field_${fields[0].id}`
  const entries = groupByMetadata[fieldKey] || []
  let y = 0
  for (const entry of entries) {
    const matches = fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      true
    )
    if (matches) {
      return { y, count: entry.count }
    }
    y += getGroupVirtualHeight({
      groupValues: getGroupValues(entry, fieldsAtDepth),
      count: entry.count,
      depth: 0,
      groupByMetadata,
      collapsedGroups,
      collapsedGroupsMode,
      fields,
      registry,
    })
  }
  return null
}

export const GROUP_HEADER_HEIGHT = HEADER_HEIGHT
export const GROUP_ROW_HEIGHT = ROW_HEIGHT

/**
 * Stable string key for a path object so set-membership checks against
 * loadedSubtrees / loadingSubtrees are O(1). The order of fields in the
 * returned key is the group-by order — i.e. the natural order the user sees.
 */
export function pathKey(path, fields) {
  if (!path || !fields) return ''
  const parts = []
  for (const field of fields) {
    const k = `field_${field.id}`
    if (!Object.prototype.hasOwnProperty.call(path, k)) break
    parts.push(JSON.stringify(path[k]))
  }
  return parts.join('|')
}

/**
 * Builds a flat virtual layout for the entire grid given the (possibly
 * partial) group-tree returned by the backend `group-tree` endpoint and the
 * user's collapse state.
 *
 * The returned `items` array describes every header, block of rows, and
 * subtree-skeleton placeholder in display order. `prefixSums[i]` is the
 * y-coordinate of `items[i]`'s top (and `prefixSums[items.length]` is
 * `totalHeight`).
 *
 * Tree input shape: ordered list of `{path, depth, row_count, children_count}`
 * where children of a node always immediately follow that node when their
 * subtree has been fetched. For non-leaf nodes whose subtree hasn't been
 * fetched yet (lazy mode), the heightIndex emits a `subtree-skeleton`
 * placeholder sized via ``children_count × HEADER_HEIGHT`` so the layout
 * doesn't pop when the response lands.
 *
 * @param loadedSubtrees Optional Set<pathKey>. When provided, expanded
 *   non-leaf paths NOT in this set get a skeleton placeholder rather than
 *   walking their (missing) descendants. ``null``/omitted = legacy mode
 *   (treats every expanded subtree as fully loaded).
 * @param loadingSubtrees Optional Set<pathKey>. When set, marks the
 *   skeleton item with ``loading: true`` so the renderer can show a spinner.
 */
export function buildHeightIndex({
  treeNodes,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
  loadedSubtrees = null,
  loadingSubtrees = null,
}) {
  const items = []
  const prefixSums = [0]
  let cumulativeHeight = 0
  let visibleRowCount = 0
  // Depth at which the current collapse roots (null = no active collapse).
  // Once set, descendants are skipped until we encounter a sibling/shallower
  // node, which resets it.
  let openCollapseDepth = null

  if (!treeNodes || treeNodes.length === 0 || !fields || fields.length === 0) {
    return Object.freeze({
      items: Object.freeze(items),
      prefixSums: Float64Array.from(prefixSums),
      totalHeight: 0,
      totalRowCount: 0,
    })
  }

  const maxDepth = fields.length - 1

  const isSubtreeLoaded = (node) => {
    if (loadedSubtrees === null) return true
    const key = pathKey(node.path, fields.slice(0, node.depth + 1))
    return loadedSubtrees.has(key)
  }

  const isSubtreeLoading = (node) => {
    if (loadingSubtrees === null) return false
    const key = pathKey(node.path, fields.slice(0, node.depth + 1))
    return loadingSubtrees.has(key)
  }

  for (const node of treeNodes) {
    if (openCollapseDepth !== null && node.depth <= openCollapseDepth) {
      openCollapseDepth = null
    }

    if (openCollapseDepth !== null) {
      continue
    }

    const fieldsAtDepth = fields.slice(0, node.depth + 1)
    const collapsed = isCollapsed(
      collapsedGroups,
      node.path,
      fieldsAtDepth,
      registry,
      collapsedGroupsMode,
      true
    )

    const rowCount = node.row_count ?? node.count ?? 0
    const childrenCount = node.children_count ?? null

    items.push({
      type: 'group-header',
      depth: node.depth,
      path: node.path,
      rowCount,
      childrenCount,
      collapsed,
      startRowIndex: visibleRowCount,
      y: cumulativeHeight,
    })
    cumulativeHeight += HEADER_HEIGHT
    prefixSums.push(cumulativeHeight)

    if (collapsed) {
      openCollapseDepth = node.depth
      continue
    }

    if (node.depth === maxDepth) {
      items.push({
        type: 'rows',
        depth: node.depth,
        path: node.path,
        count: rowCount,
        startRowIndex: visibleRowCount,
        y: cumulativeHeight,
      })
      cumulativeHeight += rowCount * ROW_HEIGHT
      visibleRowCount += rowCount
      prefixSums.push(cumulativeHeight)
    } else if (!isSubtreeLoaded(node)) {
      // Non-leaf, expanded, subtree not yet fetched. Reserve space for
      // ``children_count`` collapsed sub-headers so the layout doesn't pop
      // when the response lands; mark the placeholder loading=true so the
      // renderer can show a spinner.
      const placeholderHeight = (childrenCount || 0) * HEADER_HEIGHT
      items.push({
        type: 'subtree-skeleton',
        depth: node.depth,
        path: node.path,
        childrenCount,
        loading: isSubtreeLoading(node),
        startRowIndex: visibleRowCount,
        y: cumulativeHeight,
        height: placeholderHeight,
      })
      cumulativeHeight += placeholderHeight
      prefixSums.push(cumulativeHeight)
      // Skip the natural-iteration walk through descendants — we won't
      // encounter any in `treeNodes` anyway because the subtree isn't
      // loaded; this just makes the intent explicit.
      openCollapseDepth = node.depth
    }
  }

  // Annotate every header with the visible-row range it covers. The render
  // path uses this to skip emitting deep-level headers whose group falls
  // entirely outside the buffer window — without it a view with thousands of
  // leaf groups would push thousands of header nodes into the DOM on every
  // toggle.
  const headerStack = []
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (item.type !== 'group-header') continue
    while (
      headerStack.length > 0 &&
      items[headerStack[headerStack.length - 1]].depth >= item.depth
    ) {
      const closedIdx = headerStack.pop()
      items[closedIdx].endRowIndex = item.startRowIndex
    }
    item.endRowIndex = visibleRowCount
    headerStack.push(i)
  }
  while (headerStack.length > 0) {
    const idx = headerStack.pop()
    items[idx].endRowIndex = visibleRowCount
  }

  // Freeze so Vuex doesn't recursively wrap each item / path object in a
  // reactive proxy when the index is committed to state. Reactive proxying
  // for thousands of nodes is a real CPU cost and we only ever read this
  // structure — never mutate it in place.
  return Object.freeze({
    items: Object.freeze(items),
    prefixSums: Float64Array.from(prefixSums),
    totalHeight: cumulativeHeight,
    totalRowCount: visibleRowCount,
  })
}

/**
 * Maps a visible-row index back to its y-coordinate in the height index.
 * Used to anchor the rendered buffer at the right pixel offset when the
 * grid view contains a mix of headers and rows. Returns 0 for an empty index.
 *
 * `buildInterleavedList` prepends a depth-0 header to the buffer whenever the
 * buffer starts exactly at the first row of a top-level group, so for those
 * boundary cases this returns the *header*'s y rather than the row's. When
 * the buffer starts mid-group, no header is prepended and we return the y of
 * the row itself.
 */
export function rowOffsetToY(heightIndex, rowOffset) {
  if (!heightIndex || !heightIndex.items || heightIndex.items.length === 0) {
    return 0
  }
  const target = Math.max(0, rowOffset)

  for (const item of heightIndex.items) {
    if (
      item.type === 'group-header' &&
      item.depth === 0 &&
      item.startRowIndex === target
    ) {
      return item.y
    }
  }

  for (const item of heightIndex.items) {
    if (item.type !== 'rows') continue
    if (target < item.startRowIndex) {
      return item.y
    }
    if (target < item.startRowIndex + item.count) {
      return item.y + (target - item.startRowIndex) * ROW_HEIGHT
    }
  }
  return heightIndex.totalHeight
}

/**
 * Fast path for the renderable interleaved list when a height index is
 * available. Walks the prebuilt `items` array — already in display order,
 * already collapse-aware — and emits headers + rows in the buffer's window.
 *
 * O(items + buffer_rows). The legacy `buildInterleavedList` is O(metadata *
 * items * metadata) due to nested findIndex/some calls; for views with many
 * leaf groups this becomes a CPU bottleneck on every collapse toggle, which
 * is what this function avoids.
 */
export function buildInterleavedFromHeightIndex({
  heightIndex,
  rows,
  bufferStartIndex,
  fields,
}) {
  if (!heightIndex || !heightIndex.items || heightIndex.items.length === 0) {
    return rows.map((row) => ({ type: 'row', row }))
  }
  const items = heightIndex.items
  const out = []
  const bufferEndIndex = bufferStartIndex + rows.length
  const headerEndIndex = bufferEndIndex

  for (const item of items) {
    if (item.type === 'group-header') {
      // Headers are emitted only when the group's row range overlaps the
      // buffer. Without this gate, depth-0 headers far below the buffer
      // (e.g. ``Design`` after Accounting's just-expanded 1383 rows) would
      // render in DOM-flow right after the buffer's last row, while the
      // heightIndex says they live ~22 000 px further down — producing the
      // "all the headers stack at the bottom and only fix when rows arrive"
      // glitch.
      //
      // Inclusive overlap test (`start > end` / `end < start` skip): a
      // header whose group has zero visible rows (e.g. a collapsed sibling
      // under a just-expanded parent) has start == end, and we want it on
      // screen. Strict-greater would silently drop those, leaving the user
      // with only the parent header and a blank viewport.
      const itemStart = item.startRowIndex
      const itemEnd = item.endRowIndex ?? itemStart
      if (itemStart > headerEndIndex || itemEnd < bufferStartIndex) {
        continue
      }
      out.push({
        type: 'header',
        depth: item.depth,
        field: fields[item.depth],
        groupValues: item.path,
        count: item.rowCount,
        childrenCount: item.childrenCount,
        collapsed: item.collapsed,
      })
    } else if (item.type === 'rows') {
      const visibleStart = Math.max(item.startRowIndex, bufferStartIndex)
      const visibleEnd = Math.min(
        item.startRowIndex + item.count,
        bufferEndIndex
      )
      for (let i = visibleStart; i < visibleEnd; i++) {
        const row = rows[i - bufferStartIndex]
        if (row) out.push({ type: 'row', row })
      }
    } else if (item.type === 'subtree-skeleton') {
      out.push({
        type: 'subtree-skeleton',
        depth: item.depth,
        path: item.path,
        childrenCount: item.childrenCount,
        loading: item.loading,
        height: item.height,
      })
    }
  }

  return out
}

/**
 * Binary-searches the prefix-sum array to map a viewport `scrollTop` pixel
 * value to the item at that position, plus the visible-row offset the row
 * fetcher should request. Returns `null` when the index is empty.
 */
export function resolveScrollTop(heightIndex, scrollTop) {
  const { items, prefixSums, totalHeight } = heightIndex
  if (!items || items.length === 0) return null

  const clamped = Math.max(0, Math.min(scrollTop, totalHeight))
  let lo = 0
  let hi = items.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >>> 1
    if (prefixSums[mid] <= clamped) {
      lo = mid
    } else {
      hi = mid - 1
    }
  }

  const itemIndex = lo
  const item = items[itemIndex]
  const y = prefixSums[itemIndex]
  const offsetWithinItem = clamped - y

  let rowOffset = item.startRowIndex
  if (item.type === 'rows') {
    rowOffset += Math.min(
      Math.max(Math.floor(offsetWithinItem / ROW_HEIGHT), 0),
      Math.max(item.count - 1, 0)
    )
  }

  return { itemIndex, item, y, offsetWithinItem, rowOffset }
}

function getGroupVirtualHeight({
  groupValues,
  count,
  depth,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
}) {
  const fieldsAtDepth = fields.slice(0, depth + 1)
  let height = HEADER_HEIGHT

  if (
    isCollapsed(
      collapsedGroups,
      groupValues,
      fieldsAtDepth,
      registry,
      collapsedGroupsMode
    )
  ) {
    return height
  }

  if (depth === fields.length - 1) {
    return height + count * ROW_HEIGHT
  }

  const childDepth = depth + 1
  const childField = fields[childDepth]
  const childEntries = groupByMetadata[`field_${childField.id}`] || []
  const children = childEntries.filter((entry) =>
    fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      true
    )
  )

  if (children.length === 0) {
    return height + count * ROW_HEIGHT
  }

  return (
    height +
    children.reduce((total, childEntry) => {
      const childFields = fields.slice(0, childDepth + 1)
      return (
        total +
        getGroupVirtualHeight({
          groupValues: getGroupValues(childEntry, childFields),
          count: childEntry.count,
          depth: childDepth,
          groupByMetadata,
          collapsedGroups,
          collapsedGroupsMode,
          fields,
          registry,
        })
      )
    }, 0)
  )
}

export function buildInterleavedList({
  rows,
  activeGroupBys,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  registry,
  fields = [],
  bufferStartIndex = 0,
}) {
  if (activeGroupBys.length === 0) {
    return rows.map((row) => ({ type: 'row', row }))
  }

  const groupByFields = activeGroupBys
    .map(
      (groupBy, index) =>
        fields.find((field) => field.id === groupBy.field) || fields[index]
    )
    .filter(Boolean)

  if (groupByFields.length === 0) {
    return rows.map((row) => ({ type: 'row', row }))
  }

  const items = []

  rows.forEach((row, index) => {
    const previousRow = rows[index - 1]
    const rowIndex = bufferStartIndex + index
    let skipRow = false

    for (let depth = 0; depth < groupByFields.length; depth++) {
      const fieldsAtDepth = groupByFields.slice(0, depth + 1)
      const groupValues = getGroupValues(row, fieldsAtDepth)

      if (
        isAncestorCollapsed(
          collapsedGroups,
          groupValues,
          groupByFields,
          depth,
          registry,
          false,
          collapsedGroupsMode
        )
      ) {
        skipRow = true
        break
      }

      const isNewGroup =
        previousRow === undefined ||
        !fieldValuesAreEqualInObjects(fieldsAtDepth, registry, previousRow, row)

      const metadataEntry = lookupMetadataEntry(
        groupByMetadata,
        groupByFields,
        depth,
        groupValues,
        registry
      )
      const serializedGroupValues = metadataEntry
        ? getGroupValues(metadataEntry, fieldsAtDepth)
        : groupValues
      const collapsed = isCollapsed(
        collapsedGroups,
        groupValues,
        fieldsAtDepth,
        registry,
        collapsedGroupsMode
      )

      const isRealGroupBoundary =
        previousRow !== undefined ||
        isGroupAtVisibleRowIndex({
          groupValues: serializedGroupValues,
          depth,
          rowIndex,
          groupByMetadata,
          collapsedGroups,
          collapsedGroupsMode,
          fields: groupByFields,
          registry,
        })

      if (isNewGroup && isRealGroupBoundary) {
        items.push({
          type: 'header',
          depth,
          field: groupByFields[depth],
          groupValues: serializedGroupValues,
          count: metadataEntry?.count ?? -1,
          collapsed,
        })
      }

      if (collapsed) {
        skipRow = true
        break
      }
    }

    if (!skipRow) {
      items.push({ type: 'row', row })
    }
  })

  // Backfill missing depth-0 headers from metadata. This covers both
  // collapsed groups (whose rows the backend excluded) and the brief window
  // after a user re-expands a group, before the new rows arrive — without it
  // the header would vanish until the next refresh completes.
  insertMissingDepth0Headers(
    items,
    groupByMetadata,
    collapsedGroups,
    collapsedGroupsMode,
    groupByFields,
    registry,
    bufferStartIndex,
    rows.length
  )

  insertCollapsedGroupHeaders(
    items,
    groupByMetadata,
    collapsedGroups,
    collapsedGroupsMode,
    groupByFields,
    registry
  )

  return items
}

function getGroupValues(row, fields) {
  return fields.reduce((values, field) => {
    values[`field_${field.id}`] = row[`field_${field.id}`]
    return values
  }, {})
}

function isGroupAtVisibleRowIndex({
  groupValues,
  depth,
  rowIndex,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
}) {
  const groupStartRowIndex = findGroupStartRowIndex({
    groupValues,
    depth,
    groupByMetadata,
    collapsedGroups,
    collapsedGroupsMode,
    fields,
    registry,
  })
  return groupStartRowIndex === rowIndex
}

function findGroupStartRowIndex({
  groupValues,
  depth,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
}) {
  let rowIndex = 0

  function visitGroups(currentDepth, parentValues = null) {
    const field = fields[currentDepth]
    const fieldsAtDepth = fields.slice(0, currentDepth + 1)
    const parentFields = fields.slice(0, currentDepth)
    const entries = groupByMetadata[`field_${field.id}`] || []

    for (const entry of entries) {
      if (
        parentValues !== null &&
        !fieldValuesAreEqualInObjects(
          parentFields,
          registry,
          entry,
          parentValues,
          true,
          true
        )
      ) {
        continue
      }

      const entryGroupValues = getGroupValues(entry, fieldsAtDepth)
      const matchesTarget = fieldValuesAreEqualInObjects(
        fieldsAtDepth,
        registry,
        entryGroupValues,
        groupValues,
        true,
        true
      )

      if (currentDepth === depth && matchesTarget) {
        return rowIndex
      }

      if (
        currentDepth < depth &&
        fieldValuesAreEqualInObjects(
          fieldsAtDepth,
          registry,
          entryGroupValues,
          groupValues,
          true,
          true
        )
      ) {
        return visitGroups(currentDepth + 1, entryGroupValues)
      }

      rowIndex += getGroupVisibleRowCount({
        groupValues: entryGroupValues,
        count: entry.count,
        depth: currentDepth,
        groupByMetadata,
        collapsedGroups,
        collapsedGroupsMode,
        fields,
        registry,
      })
    }

    return null
  }

  return visitGroups(0)
}

function getGroupVisibleRowCount({
  groupValues,
  count,
  depth,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
}) {
  const fieldsAtDepth = fields.slice(0, depth + 1)
  const collapsed = isCollapsed(
    collapsedGroups,
    groupValues,
    fieldsAtDepth,
    registry,
    collapsedGroupsMode,
    true
  )

  if (collapsed) {
    return 0
  }

  if (depth === fields.length - 1) {
    return count
  }

  const childDepth = depth + 1
  const childField = fields[childDepth]
  const childEntries = groupByMetadata[`field_${childField.id}`] || []
  const children = childEntries.filter((entry) =>
    fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      true
    )
  )

  if (children.length === 0) {
    return count
  }

  return children.reduce((total, childEntry) => {
    const childFields = fields.slice(0, childDepth + 1)
    return (
      total +
      getGroupVisibleRowCount({
        groupValues: getGroupValues(childEntry, childFields),
        count: childEntry.count,
        depth: childDepth,
        groupByMetadata,
        collapsedGroups,
        collapsedGroupsMode,
        fields,
        registry,
      })
    )
  }, 0)
}

function lookupMetadataEntry(
  metadata,
  fields,
  depth,
  groupValues,
  registry,
  groupValuesIsGroup = false
) {
  const field = fields[depth]
  const fieldKey = `field_${field.id}`
  const entries = metadata[fieldKey] || []
  const fieldsAtDepth = fields.slice(0, depth + 1)
  return entries.find((entry) =>
    fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      groupValuesIsGroup
    )
  )
}

function isCollapsed(
  collapsedGroups,
  groupValues,
  fieldsAtDepth,
  registry,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  groupValuesIsGroup = false
) {
  const inList = collapsedGroups.some((entry) => {
    if (Object.keys(entry).length !== fieldsAtDepth.length) {
      return false
    }
    // collapsedGroup holds metadata-form values (e.g. an option ID); groupValues
    // holds row-form values (e.g. {id, value, color}). Pass object1IsGroup so
    // the metadata side is converted via getRowValueFromGroupValue first.
    return fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      groupValuesIsGroup
    )
  })

  return collapsedGroupsMode === COLLAPSED_GROUPS_MODE_COLLAPSE
    ? !inList
    : inList
}

function isAncestorCollapsed(
  collapsedGroups,
  groupValues,
  groupByFields,
  depth,
  registry,
  groupValuesIsGroup = false,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND
) {
  for (let ancestorDepth = 0; ancestorDepth < depth; ancestorDepth++) {
    const fieldsAtDepth = groupByFields.slice(0, ancestorDepth + 1)
    const ancestorValues = fieldsAtDepth.reduce((acc, f) => {
      acc[`field_${f.id}`] = groupValues[`field_${f.id}`]
      return acc
    }, {})
    if (
      isCollapsed(
        collapsedGroups,
        ancestorValues,
        fieldsAtDepth,
        registry,
        collapsedGroupsMode,
        groupValuesIsGroup
      )
    ) {
      return true
    }
  }
  return false
}

function insertMissingDepth0Headers(
  items,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry,
  bufferStartIndex,
  bufferLength
) {
  if (fields.length === 0) {
    return
  }
  const field = fields[0]
  const fieldsAtDepth = [field]
  const fieldKey = `field_${field.id}`
  const metadataEntries = groupByMetadata[fieldKey] || []

  metadataEntries.forEach((entry, metadataIndex) => {
    const groupValues = getGroupValues(entry, fieldsAtDepth)
    const collapsed = isCollapsed(
      collapsedGroups,
      groupValues,
      fieldsAtDepth,
      registry,
      collapsedGroupsMode,
      true
    )

    // In expand-mode, only synthesize headers for collapsed groups — uncollapsed
    // ones get their headers from the row-iteration above, anchored to the real
    // row positions in the buffer. Synthesizing them here would put them at
    // the wrong virtual y when the buffer sits mid-group.
    //
    // In collapse-mode every group is conceptually a header-tall placeholder by
    // default, including the just-toggled exception whose rows haven't arrived
    // yet. Synthesize for all entries; `alreadyRendered` deduplicates against
    // headers the row-iteration already added once the response lands.
    if (collapsedGroupsMode === COLLAPSED_GROUPS_MODE_EXPAND && !collapsed) {
      return
    }

    if (collapsedGroupsMode === COLLAPSED_GROUPS_MODE_EXPAND && collapsed) {
      const groupStartRowIndex = findGroupStartRowIndex({
        groupValues,
        depth: 0,
        groupByMetadata,
        collapsedGroups,
        collapsedGroupsMode,
        fields,
        registry,
      })
      if (
        groupStartRowIndex === null ||
        groupStartRowIndex < bufferStartIndex ||
        groupStartRowIndex > bufferStartIndex + bufferLength
      ) {
        return
      }
    }

    const alreadyRendered = items.some(
      (item) =>
        item.type === 'header' &&
        item.depth === 0 &&
        fieldValuesAreEqualInObjects(
          fieldsAtDepth,
          registry,
          item.groupValues,
          groupValues,
          true,
          true
        )
    )
    if (alreadyRendered) {
      return
    }

    const insertIndex = items.findIndex((item) => {
      if (item.type !== 'header' || item.depth !== 0) {
        return false
      }
      const itemMetadataIndex = metadataEntries.findIndex((e) =>
        fieldValuesAreEqualInObjects(
          fieldsAtDepth,
          registry,
          e,
          item.groupValues,
          true,
          true
        )
      )
      const resolvedIndex =
        itemMetadataIndex === -1 ? Number.MAX_SAFE_INTEGER : itemMetadataIndex
      return metadataIndex < resolvedIndex
    })

    items.splice(insertIndex === -1 ? items.length : insertIndex, 0, {
      type: 'header',
      depth: 0,
      field,
      groupValues,
      count: entry.count,
      collapsed,
    })
  })
}

function insertCollapsedGroupHeaders(
  items,
  groupByMetadata,
  collapsedGroups,
  collapsedGroupsMode = COLLAPSED_GROUPS_MODE_EXPAND,
  fields,
  registry
) {
  for (let depth = 1; depth < fields.length; depth++) {
    const field = fields[depth]
    const fieldsAtDepth = fields.slice(0, depth + 1)
    const metadataEntries = groupByMetadata[`field_${field.id}`] || []

    metadataEntries.forEach((entry) => {
      const groupValues = getGroupValues(entry, fieldsAtDepth)
      const collapsed = isCollapsed(
        collapsedGroups,
        groupValues,
        fieldsAtDepth,
        registry,
        collapsedGroupsMode,
        true
      )

      // Same rule as `insertMissingDepth0Headers`: in expand-mode skip
      // uncollapsed groups (their headers come from row-iteration), in
      // collapse-mode synthesize everything so a just-toggled exception
      // doesn't blink out of existence while the refresh is in flight.
      if (collapsedGroupsMode === COLLAPSED_GROUPS_MODE_EXPAND && !collapsed) {
        return
      }

      if (
        isAncestorCollapsed(
          collapsedGroups,
          groupValues,
          fields,
          depth,
          registry,
          true,
          collapsedGroupsMode
        )
      ) {
        return
      }

      const alreadyRendered = items.some(
        (item) =>
          item.type === 'header' &&
          item.depth === depth &&
          fieldValuesAreEqualInObjects(
            fieldsAtDepth,
            registry,
            item.groupValues,
            groupValues,
            true,
            true
          )
      )

      if (alreadyRendered) {
        return
      }

      // Only insert a deeper-level collapsed header if its parent group is
      // present in the items list — otherwise we'd plant a Design+High header
      // somewhere inside Development's section because there's no Design
      // anchor to position it against.
      const parentFields = fields.slice(0, depth)
      const parentValues = parentFields.reduce((acc, parentField) => {
        acc[`field_${parentField.id}`] = groupValues[`field_${parentField.id}`]
        return acc
      }, {})
      const parentItemIndex = items.findIndex(
        (item) =>
          item.type === 'header' &&
          item.depth === depth - 1 &&
          fieldValuesAreEqualInObjects(
            parentFields,
            registry,
            item.groupValues,
            parentValues,
            true,
            true
          )
      )
      if (parentItemIndex === -1) {
        return
      }

      const header = {
        type: 'header',
        depth,
        field,
        groupValues,
        count: entry.count,
        collapsed,
      }

      // Find the next sibling at this depth WITHIN the same parent. We bound
      // the search to the parent's section so we only consider items that
      // belong to it.
      const collapsedMetadataIndex = findMetadataIndex(
        metadataEntries,
        groupValues,
        fieldsAtDepth,
        registry
      )

      let parentSectionEnd = items.length
      for (let i = parentItemIndex + 1; i < items.length; i++) {
        const item = items[i]
        if (item.type === 'header' && item.depth <= depth - 1) {
          parentSectionEnd = i
          break
        }
      }

      let insertIndex = -1
      for (let i = parentItemIndex + 1; i < parentSectionEnd; i++) {
        const item = items[i]
        if (item.type !== 'header' || item.depth !== depth) continue
        const itemMetadataIndex = findMetadataIndex(
          metadataEntries,
          item.groupValues,
          fieldsAtDepth,
          registry
        )
        if (collapsedMetadataIndex < itemMetadataIndex) {
          insertIndex = i
          break
        }
      }

      items.splice(
        insertIndex === -1 ? parentSectionEnd : insertIndex,
        0,
        header
      )
    })
  }
}

function findMetadataIndex(entries, groupValues, fieldsAtDepth, registry) {
  const index = entries.findIndex((entry) =>
    fieldValuesAreEqualInObjects(
      fieldsAtDepth,
      registry,
      entry,
      groupValues,
      true,
      true
    )
  )
  return index === -1 ? Number.MAX_SAFE_INTEGER : index
}
