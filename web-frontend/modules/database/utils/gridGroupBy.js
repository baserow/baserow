import { pathKey } from '@baserow/modules/database/utils/gridGroupByRender'
import { computeRowInsertPosition } from '@baserow/modules/database/utils/row'
import { getRowSortFunction } from '@baserow/modules/database/utils/view'
import { DEFAULT_SORT_TYPE_KEY } from '@baserow/modules/database/constants'

/**
 * Pure helpers for the grid view's group-by data model, extracted from the grid store
 * so the store keeps only Vuex state, mutations and actions. None of these touch store
 * state — they operate purely on their arguments and are unit-testable in isolation.
 */

/**
 * The collapse state for "collapse all" / "expand all": an empty exception list with
 * the matching mode.
 */
export function getGroupByCollapseAllState(collapse) {
  return collapse
    ? { mode: 'collapse', paths: [] }
    : { mode: 'expand', paths: [] }
}

/**
 * True only when the whole tree is uniformly collapsed (no per-group exceptions),
 * where every group renders just its top-level header, so the store can page by
 * depth. Expanded and mixed states page per parent instead, so one request returns
 * a parent's whole subtree down to its leaves.
 */
export function shouldUseGroupByDepthPages(groupBy) {
  return (
    groupBy.collapseInitialized === true &&
    groupBy.collapse?.mode === 'collapse' &&
    (groupBy.collapse.paths || []).length === 0
  )
}

/**
 * Resolves the active group-bys to their full field objects, in group-by order.
 */
export function getGroupByFieldsFromActiveGroupBys(activeGroupBys, fields) {
  return activeGroupBys
    .map((groupBy) => fields.find((field) => field.id === groupBy.field))
    .filter(Boolean)
}

/**
 * Whether the existing collapse paths still fit the new fields: true only when the
 * leading field order is unchanged. Used when re-projecting collapse state.
 */
function canProjectGroupByCollapseState(
  collapse,
  previousGroupByFields,
  groupByFields
) {
  const previousFields = previousGroupByFields || []

  if (previousFields.length === 0) {
    return (collapse.paths || []).every((path) => {
      const firstField = groupByFields[0]
      return !firstField || `field_${firstField.id}` in path
    })
  }

  const matchingPrefixLength = Math.min(
    previousFields.length,
    groupByFields.length
  )
  for (let index = 0; index < matchingPrefixLength; index += 1) {
    if (previousFields[index].id !== groupByFields[index].id) {
      return false
    }
  }
  return true
}

/**
 * Re-projects a collapse state onto a new set of group-by fields when the leading
 * field order is unchanged. This keeps collapse state for add/remove of trailing
 * levels, but resets it for reorders/replacements where old paths would feel wrong.
 */
export function projectGroupByCollapseState(
  collapse,
  previousGroupByFields,
  groupByFields
) {
  if (!collapse) {
    return getGroupByCollapseAllState(false)
  }

  if (
    !canProjectGroupByCollapseState(
      collapse,
      previousGroupByFields,
      groupByFields
    )
  ) {
    return getGroupByCollapseAllState(false)
  }

  const paths = []
  const seen = new Set()

  for (const path of collapse.paths || []) {
    const projectedPath = {}

    for (const field of groupByFields) {
      const key = `field_${field.id}`
      if (!(key in path)) {
        break
      }
      projectedPath[key] = path[key]
    }

    if (Object.keys(projectedPath).length === 0) {
      continue
    }

    const projectedKey = pathKey(projectedPath, groupByFields)
    if (seen.has(projectedKey)) {
      continue
    }

    seen.add(projectedKey)
    paths.push(projectedPath)
  }

  return {
    mode: collapse.mode,
    paths,
  }
}

/**
 * Converts the sparse `sectionKey -> position-array` section rows into a
 * `sectionKey -> Map<position, row>` structure for the renderer.
 */
export function makeSectionRowsMap(sectionRows) {
  const sections = new Map()
  for (const [sectionKey, rows] of Object.entries(sectionRows)) {
    const rowMap = new Map()
    Object.keys(rows).forEach((position) => {
      const row = rows[position]
      if (row !== undefined) {
        rowMap.set(Number(position), row)
      }
    })
    sections.set(sectionKey, rowMap)
  }
  return sections
}

/**
 * Returns the defined rows of a section in ascending position order, optionally
 * excluding a row id.
 */
export function getDefinedRowsFromSectionRows(
  sectionRows,
  sectionKey,
  excludeRowId = null
) {
  const rows = sectionRows[sectionKey] || []
  return Object.keys(rows)
    .map((position) => Number(position))
    .sort((a, b) => a - b)
    .map((position) => rows[position])
    .filter((row) => row && row.id !== excludeRowId)
}

/**
 * Iterates every defined row across all sections.
 */
export function forEachGroupByRow(sectionRows, callback) {
  for (const rows of Object.values(sectionRows)) {
    for (const position of Object.keys(rows)) {
      const row = rows[position]
      if (row !== undefined) {
        callback(row)
      }
    }
  }
}

/**
 * Carries over the transient UI state (selection) from an existing row onto a freshly
 * fetched/updated row so a re-fetch doesn't drop the user's selection.
 */
export function preserveGroupByRowUiState(row, existingRow) {
  if (!existingRow?._ || !row?._) {
    return row
  }

  return {
    ...row,
    _: {
      ...row._,
      selected: existingRow._.selected,
      selectedFieldId: existingRow._.selectedFieldId,
      selectedBy: [...(existingRow._.selectedBy || [])],
    },
  }
}

/**
 * Default row values for a new row created in a group, taken from the group path.
 * Used by the store when adding a row to a group.
 */
export function groupPathDefaults(path, fields, registry) {
  const values = {}
  for (const field of fields) {
    const fieldKey = `field_${field.id}`
    if (!(fieldKey in path)) {
      continue
    }
    const fieldType = registry.get('field', field.type)
    if (!fieldType.canWriteFieldValues(field)) {
      continue
    }
    values[fieldKey] = fieldType.getRowValueFromGroupValue(
      field,
      path[fieldKey]
    )
  }
  return values
}

/**
 * Which group a row belongs to (its group-by path), from the row's field values.
 */
export function groupPathFromRow(row, fields, registry) {
  const path = {}
  for (const field of fields) {
    const fieldKey = `field_${field.id}`
    const fieldType = registry.get('field', field.type)
    path[fieldKey] = fieldType.getGroupValueFromRowValue(field, row[fieldKey])
  }
  return path
}

/**
 * How many leading group-by levels a path specifies.
 */
export function getGroupByPathDepth(path, fields) {
  let depth = 0
  for (const field of fields) {
    if (!(`field_${field.id}` in path)) {
      break
    }
    depth += 1
  }
  return depth
}

/**
 * The path trimmed to `depth` levels (an ancestor path).
 */
export function getGroupByPathPrefix(path, fields, depth) {
  const prefix = {}
  for (const field of fields.slice(0, depth + 1)) {
    const fieldKey = `field_${field.id}`
    if (fieldKey in path) {
      prefix[fieldKey] = path[fieldKey]
    }
  }
  return prefix
}

/**
 * Whether two paths are the same group at `depth`.
 */
export function groupByPathsMatchAtDepth(leftPath, rightPath, fields, depth) {
  const depthFields = fields.slice(0, depth + 1)
  return pathKey(leftPath, depthFields) === pathKey(rightPath, depthFields)
}

/**
 * Whether two paths are siblings (same parent group) at `depth`.
 */
export function groupByPathsHaveSameParent(leftPath, rightPath, fields, depth) {
  if (depth === 0) {
    return true
  }
  const parentFields = fields.slice(0, depth)
  return pathKey(leftPath, parentFields) === pathKey(rightPath, parentFields)
}

/**
 * A node's row count, accepting either `row_count` or `rowCount`.
 */
export function getGroupByNodeRowCount(node) {
  return node.row_count ?? node.rowCount ?? 0
}

/**
 * Turns a group value into a row-shaped value the sort comparator understands
 * (resolves a single-select id to its option).
 */
function getGroupBySortRowValue(field, groupValue, registry) {
  const fieldType = registry.get('field', field.type)
  const rowValue = fieldType.getRowValueFromGroupValue(field, groupValue)

  if (
    field.type === 'single_select' &&
    rowValue !== null &&
    typeof rowValue === 'object' &&
    rowValue.id !== undefined &&
    rowValue.value === undefined
  ) {
    return (
      (field.select_options || []).find(
        (option) => option.id === rowValue.id
      ) || rowValue
    )
  }

  return rowValue
}

/**
 * Builds a stand-in row from a node's path so it can be run through the row sorter.
 */
function groupByNodeToSortRow(node, fields, registry) {
  const row = {
    id: 0,
    order: '0',
  }

  for (const field of fields) {
    const fieldKey = `field_${field.id}`
    if (!(fieldKey in node.path)) {
      continue
    }
    row[fieldKey] = getGroupBySortRowValue(field, node.path[fieldKey], registry)
  }

  return row
}

/**
 * The group-bys that apply at a given depth, with order/type defaults filled in.
 */
function getGroupBysForNodeDepth(groupBys, fields, depth) {
  const groupedFieldIds = new Set(
    fields.slice(0, depth + 1).map((field) => field.id)
  )
  return (groupBys || [])
    .filter((groupBy) => groupedFieldIds.has(groupBy.field))
    .map((groupBy) => ({
      ...groupBy,
      order: groupBy.order || 'ASC',
      type: groupBy.type || DEFAULT_SORT_TYPE_KEY,
    }))
}

/**
 * Orders two sibling nodes the way their rows would sort.
 */
function compareGroupByNodeSiblingOrder(
  leftNode,
  rightNode,
  fields,
  groupBys,
  registry
) {
  if (!registry) {
    return 0
  }

  const depth = leftNode.depth ?? 0
  const depthGroupBys = getGroupBysForNodeDepth(groupBys, fields, depth)
  if (depthGroupBys.length === 0) {
    return 0
  }

  const sortFunction = getRowSortFunction(registry, [], fields, depthGroupBys)
  return sortFunction(
    groupByNodeToSortRow(leftNode, fields, registry),
    groupByNodeToSortRow(rightNode, fields, registry)
  )
}

/**
 * The index just past a node and all its descendants in a flat node list.
 */
export function getAfterGroupByNodeSubtreeIndex(nodes, index) {
  const depth = nodes[index].depth ?? 0
  let nextIndex = index + 1
  while (nextIndex < nodes.length && (nodes[nextIndex].depth ?? 0) > depth) {
    nextIndex += 1
  }
  return nextIndex
}

/**
 * Where to insert a new node among its siblings to keep them sorted.
 */
export function findGroupByNodeInsertionIndex(
  nodes,
  node,
  fields,
  groupBys,
  registry
) {
  let insertionIndex = nodes.length
  const depth = node.depth ?? 0
  for (let index = 0; index < nodes.length; index += 1) {
    const current = nodes[index]
    if ((current.depth ?? 0) !== depth) {
      continue
    }
    if (!groupByPathsHaveSameParent(current.path, node.path, fields, depth)) {
      continue
    }
    if (
      compareGroupByNodeSiblingOrder(
        node,
        current,
        fields,
        groupBys,
        registry
      ) < 0
    ) {
      return index
    }
    insertionIndex = getAfterGroupByNodeSubtreeIndex(nodes, index)
  }
  return insertionIndex
}

/**
 * Recomputes every node's `sibling_index` and `row_offset` after the tree changes.
 */
export function reindexGroupByTreeSiblingMetadata(nodes, fields) {
  const updated = nodes.map((node) => ({ ...node }))

  const assign = (parentPath, depth, baseRowOffset) => {
    if (depth >= fields.length) {
      return
    }
    const siblings = updated.filter(
      (node) =>
        (node.depth ?? 0) === depth &&
        groupByPathsHaveSameParent(node.path, parentPath, fields, depth)
    )
    let rowOffset = baseRowOffset
    siblings.forEach((node, index) => {
      node.sibling_index = index
      node.row_offset = rowOffset
      rowOffset += getGroupByNodeRowCount(node)
      assign(node.path, depth + 1, node.row_offset)
    })
  }

  assign({}, 0, 0)
  return updated
}

/**
 * Applies a row-count change (`delta`) to each group along a path, adding or
 * updating nodes. Used by the store for optimistic row add/move/delete.
 */
export function updateGroupByTreeNodesForPath(
  nodes,
  path,
  fields,
  delta,
  groupBys,
  registry,
  forceSiblingMetadata = false
) {
  let updated = [...nodes]
  const pathDepth = getGroupByPathDepth(path, fields)
  const hasSiblingMetadata = updated.some(
    (node) => 'sibling_index' in node || 'row_offset' in node
  )

  for (let depth = 0; depth < pathDepth; depth += 1) {
    const targetPath = getGroupByPathPrefix(path, fields, depth)
    const existingIndex = updated.findIndex(
      (node) =>
        (node.depth ?? 0) === depth &&
        groupByPathsMatchAtDepth(node.path, targetPath, fields, depth)
    )

    if (existingIndex === -1) {
      if (delta <= 0) {
        continue
      }
      const node = {
        path: targetPath,
        depth,
        row_count: delta,
      }
      const insertIndex = findGroupByNodeInsertionIndex(
        updated,
        node,
        fields,
        groupBys,
        registry
      )
      updated.splice(insertIndex, 0, node)
      continue
    }

    const current = updated[existingIndex]
    const rowCount = Math.max(0, getGroupByNodeRowCount(current) + delta)
    // Keep the emptied node at row_count 0 (don't prune here) so the tree stays valid
    // for the next server refresh. The layout hides empty leaf groups, so the banner
    // disappears from view once its last row leaves.
    updated[existingIndex] = {
      ...current,
      row_count: rowCount,
    }
  }

  return hasSiblingMetadata || forceSiblingMetadata
    ? reindexGroupByTreeSiblingMetadata(updated, fields)
    : updated
}

/**
 * A page's nodes as a list sorted by sibling order.
 */
export function getOrderedGroupByDataPageNodes(nodes) {
  return Object.entries(nodes || {})
    .map(([index, node]) => ({
      index: Number(index),
      node,
    }))
    .sort(
      (left, right) =>
        (left.node.sibling_index ?? left.index) -
        (right.node.sibling_index ?? right.index)
    )
}

/**
 * Inserts a node into a page in sort order and re-keys the nodes densely.
 */
export function insertGroupByDataPageNode(
  nodes,
  node,
  fields,
  groupBys,
  registry
) {
  const ordered = getOrderedGroupByDataPageNodes(nodes)
  let insertionIndex = ordered.length
  for (let index = 0; index < ordered.length; index += 1) {
    if (
      compareGroupByNodeSiblingOrder(
        node,
        ordered[index].node,
        fields,
        groupBys,
        registry
      ) < 0
    ) {
      insertionIndex = index
      break
    }
  }
  ordered.splice(insertionIndex, 0, { index: insertionIndex, node })
  return Object.fromEntries(
    ordered.map(({ node }, index) => [
      index,
      {
        ...node,
        sibling_index: index,
      },
    ])
  )
}

/**
 * Re-numbers a page's nodes into dense, sequential sibling indexes and row offsets.
 */
export function normalizeGroupByDataPageNodes(
  page,
  firstIndex,
  firstRowOffset
) {
  const indexedNodes = getOrderedGroupByDataPageNodes(page.nodes)
  if (indexedNodes.length === 0) {
    return {}
  }

  let rowOffset = firstRowOffset
  const normalized = {}
  indexedNodes.forEach(({ node }, index) => {
    const siblingIndex = firstIndex + index
    normalized[siblingIndex] = {
      ...node,
      sibling_index: siblingIndex,
      row_offset: rowOffset,
    }
    rowOffset += getGroupByNodeRowCount(node)
  })
  return normalized
}

/**
 * Applies a row-count change to a single group-by data page.
 */
export function updateGroupByDataPageForPath({
  page,
  path,
  fields,
  depth,
  delta,
  groupBys,
  registry,
}) {
  const targetPath = getGroupByPathPrefix(path, fields, depth)
  let nodes = { ...(page.nodes || {}) }
  const indexedNodes = Object.entries(nodes).map(([index, node]) => ({
    index: Number(index),
    node,
  }))
  const firstIndex =
    indexedNodes.length > 0
      ? Math.min(
          ...indexedNodes.map(({ index, node }) => node.sibling_index ?? index)
        )
      : 0
  const rowOffsets = indexedNodes
    .map(({ node }) => node.row_offset)
    .filter((rowOffset) => rowOffset !== undefined)
  const firstRowOffset =
    rowOffsets.length > 0
      ? Math.min(...rowOffsets)
      : (page.rowOffset ?? page.row_offset ?? 0)
  const existingIndex = Object.keys(nodes).find((index) =>
    groupByPathsMatchAtDepth(nodes[index].path, targetPath, fields, depth)
  )
  let totalSiblingCount = page.totalSiblingCount ?? indexedNodes.length

  if (existingIndex === undefined) {
    if (delta <= 0) {
      return page
    }
    const node = {
      path: targetPath,
      depth,
      row_count: delta,
      sibling_index: 0,
      row_offset: firstRowOffset,
    }
    if (depth < fields.length - 1) {
      node.children_count = 1
    }
    // insertGroupByDataPageNode returns a fully re-keyed node map; replace rather than
    // merge so a window that started at a non-zero sibling index doesn't keep its old
    // keys alongside the new dense ones (which would duplicate nodes after normalize).
    nodes = insertGroupByDataPageNode(nodes, node, fields, groupBys, registry)
    totalSiblingCount += 1
  } else {
    const current = nodes[existingIndex]
    const rowCount = Math.max(0, getGroupByNodeRowCount(current) + delta)
    // Keep emptied nodes (row_count 0) in the page for reconciliation; the layout hides
    // their banner, matching updateGroupByTreeNodesForPath.
    nodes[existingIndex] = {
      ...current,
      row_count: rowCount,
    }
  }

  return {
    ...page,
    nodes: normalizeGroupByDataPageNodes(
      { ...page, nodes },
      firstIndex,
      firstRowOffset
    ),
    totalSiblingCount,
    rowOffset: firstRowOffset,
  }
}

/**
 * The node in a page matching a path at `depth`, if any.
 */
function getGroupByDataPageNodeForPath(page, path, fields, depth) {
  return Object.values(page?.nodes || {}).find((node) =>
    groupByPathsMatchAtDepth(node.path, path, fields, depth)
  )
}

/**
 * Resolves the absolute `row_offset` of the group identified by `parentPath` from the
 * already-loaded `pages`, by looking the group up as a sibling node inside its own
 * parent's page. Returns 0 for the top level and `undefined` when the group has not
 * been loaded (so the caller can fall back to letting the server recompute it).
 */
export function getGroupByParentRowOffset(pages, parentPath, fields) {
  const parentDepth = getGroupByPathDepth(parentPath, fields)
  if (parentDepth === 0) {
    return 0
  }
  const grandParentPath = getGroupByPathPrefix(
    parentPath,
    fields,
    parentDepth - 2
  )
  const page = (pages || {})[getGroupByPageKey(grandParentPath, fields)]
  if (!page) {
    return undefined
  }
  const node = getGroupByDataPageNodeForPath(
    page,
    parentPath,
    fields,
    parentDepth - 1
  )
  return node?.row_offset
}

/**
 * Applies a row-count change across every data page a path touches. Used by the
 * store (with the tree update) for optimistic row changes.
 */
export function updateGroupByDataPagesForPath(
  pages,
  path,
  fields,
  delta,
  groupBys,
  registry
) {
  let updated = { ...(pages || {}) }
  const pathDepth = getGroupByPathDepth(path, fields)

  for (let depth = 0; depth < pathDepth; depth += 1) {
    const parentPath =
      depth === 0 ? {} : getGroupByPathPrefix(path, fields, depth - 1)
    const pageKey = pathKey(parentPath, fields)
    let page = updated[pageKey]
    if (!page && delta > 0) {
      const grandParentPath =
        depth <= 1 ? {} : getGroupByPathPrefix(path, fields, depth - 2)
      const parentNode =
        depth === 0
          ? null
          : getGroupByDataPageNodeForPath(
              updated[pathKey(grandParentPath, fields)],
              parentPath,
              fields,
              depth - 1
            )
      page = {
        parentPath,
        nodes: {},
        totalSiblingCount: 0,
        rowOffset: parentNode?.row_offset ?? 0,
      }
    }
    if (!page) {
      continue
    }

    updated = {
      ...updated,
      [pageKey]: updateGroupByDataPageForPath({
        page,
        path,
        fields,
        depth,
        delta,
        groupBys,
        registry,
      }),
    }
  }

  return updated
}

/**
 * Finds a section in the rendered layout by its section key.
 */
export function findGroupByRowSection(layout, sectionKey, fields) {
  return layout.items.find(
    (item) =>
      item.type === 'rowSection' && pathKey(item.path, fields) === sectionKey
  )
}

/**
 * Where a row should land in its section — its path, section key and absolute
 * position. Used by the store when inserting or moving a row.
 */
export function getGroupByRowInsertLocation({
  row,
  view,
  fields,
  registry,
  groupByFields,
  sectionRows,
}) {
  const path = groupPathFromRow(row, groupByFields, registry)
  const sectionKey = pathKey(path, groupByFields)
  // The section stores its rows in a sparse array keyed by their absolute position in
  // the group. Pair each loaded row with that absolute position (ascending, excluding
  // the row being placed) so the sorted slot can be mapped back to an absolute index.
  const sectionArray = sectionRows[sectionKey] || []
  const definedEntries = Object.keys(sectionArray)
    .map((position) => Number(position))
    .sort((a, b) => a - b)
    .map((position) => ({ position, row: sectionArray[position] }))
    .filter((entry) => entry.row && entry.row.id !== row.id)

  const { sortedIndex } = computeRowInsertPosition(
    row,
    definedEntries.map((entry) => entry.row),
    view.sortings ?? [],
    fields,
    registry,
    []
  )

  // `sortedIndex` is an index into the compacted defined-rows list. Translate it into an
  // absolute position so INSERT_ROW_AT_LOCATION splices correctly even when the loaded
  // window does not start at position 0 (e.g. after scrolling deep into a large group).
  // Callers that remove the row first must compute this location after the removal so
  // the surrounding positions are already reindexed.
  let position
  if (definedEntries.length === 0) {
    position = 0
  } else if (sortedIndex >= definedEntries.length) {
    position = definedEntries[definedEntries.length - 1].position + 1
  } else {
    position = definedEntries[sortedIndex].position
  }

  return {
    path,
    sectionKey,
    position,
  }
}

/**
 * Whether a row's group matches a section (true when fields/registry are unknown).
 */
export function rowBelongsToGroupBySection(row, section, fields, registry) {
  if (!row || !fields || !registry) {
    return true
  }
  const sectionPath = section.sectionPath || section.path
  if (!sectionPath) {
    return true
  }
  return (
    pathKey(groupPathFromRow(row, fields, registry), fields) ===
    pathKey(sectionPath, fields)
  )
}

/**
 * The cached row at an absolute offset, but only if it belongs to the section —
 * guards against a stale cached row landing in the wrong group.
 */
function getAbsoluteRowForGroupBySection({
  absoluteRows = {},
  absoluteOffset,
  section,
  fields,
  registry,
}) {
  const row = absoluteRows[absoluteOffset]
  if (!rowBelongsToGroupBySection(row, section, fields, registry)) {
    return undefined
  }
  return row
}

/**
 * Walks each section's [startPosition, endPosition) range and collapses the positions
 * where `isMissingAt(section, position)` is true into contiguous {startPosition,
 * endPosition} ranges (carrying the section's other fields through). Shared scan used to
 * find both missing section rows and missing absolute-row offsets.
 */
export function collectMissingSectionRanges(sections, isMissingAt) {
  const missing = []

  for (const section of sections) {
    let rangeStart = null
    const pushRange = (endPosition) => {
      if (rangeStart === null) {
        return
      }
      missing.push({ ...section, startPosition: rangeStart, endPosition })
      rangeStart = null
    }

    for (
      let position = section.startPosition;
      position < section.endPosition;
      position += 1
    ) {
      if (isMissingAt(section, position)) {
        rangeStart = rangeStart ?? position
      } else {
        pushRange(position)
      }
    }

    pushRange(section.endPosition)
  }

  return missing
}

/**
 * The position ranges in visible sections that have no row loaded yet. Used by the
 * store to decide what to fetch.
 */
export function getMissingGroupBySectionRanges(
  sectionRows,
  sections,
  absoluteRows = {},
  fields = null,
  registry = null
) {
  return collectMissingSectionRanges(sections, (section, position) => {
    const rows = sectionRows[section.sectionKey] || []
    if (rows[position] !== undefined) {
      return false
    }
    const absoluteRow = getAbsoluteRowForGroupBySection({
      absoluteRows,
      absoluteOffset: section.absoluteRowOffset + position,
      section,
      fields,
      registry,
    })
    return absoluteRow === undefined
  })
}

/**
 * The pages-map key for a parent path.
 */
function getGroupByPageKey(parentPath, fields) {
  return pathKey(parentPath || {}, fields)
}

/**
 * Whether a parent's [offset, offset+limit) sibling range is fully loaded. Used by
 * the store to skip fetches it already has.
 */
export function isGroupByDataPageLoaded(
  pages,
  parentPath,
  offset,
  limit,
  fields
) {
  const page = pages?.[getGroupByPageKey(parentPath, fields)]
  if (!page) {
    return false
  }
  const total = page.totalSiblingCount ?? 0
  if (offset >= total) {
    return true
  }
  const end = Math.min(offset + limit, total)
  for (let index = offset; index < end; index += 1) {
    if (page.nodes[index] === undefined) {
      return false
    }
  }
  return true
}

/**
 * Scatters just-fetched absolute-offset rows into their sections as contiguous
 * runs. Used by the store after loading rows by absolute offset.
 */
export function placeAbsoluteRowsIntoSections({
  absoluteRows,
  sections,
  fields = null,
  registry = null,
  isPositionLoaded = null,
}) {
  const placements = []
  const rowsByOffset = absoluteRows || {}
  sections.forEach((section) => {
    let rangeStart = null
    let rows = []
    const pushRange = () => {
      if (rangeStart === null) {
        return
      }
      placements.push({
        sectionKey: section.sectionKey,
        startPosition: rangeStart,
        rows,
      })
      rangeStart = null
      rows = []
    }

    for (
      let position = section.startPosition;
      position < section.endPosition;
      position += 1
    ) {
      // A position already materialized in the section is authoritative (e.g. a row
      // was optimistically moved there). Re-placing the absolute-offset cache over it
      // would revert the move and leave a duplicate, so treat it as a gap.
      const row =
        isPositionLoaded && isPositionLoaded(section.sectionKey, position)
          ? undefined
          : getAbsoluteRowForGroupBySection({
              absoluteRows: rowsByOffset,
              absoluteOffset: section.absoluteRowOffset + position,
              section,
              fields,
              registry,
            })
      if (row === undefined) {
        pushRange()
      } else {
        rangeStart = rangeStart ?? position
        rows.push(row)
      }
    }
    pushRange()
  })
  return placements
}

/**
 * Maps a visible row range to the absolute-offset ranges to fetch per section.
 * Used by the store when loading rows for the viewport.
 */
export function getGroupByAbsoluteRangesForVisibleRange(
  layout,
  startIndex,
  limit
) {
  const endIndex = startIndex + limit
  const ranges = []
  layout.items
    .filter((item) => item.type === 'rowSection')
    .forEach((section) => {
      const sectionVisibleStart = section.firstGlobalRowOffset
      const sectionVisibleEnd = section.firstGlobalRowOffset + section.rowCount
      const overlapStart = Math.max(startIndex, sectionVisibleStart)
      const overlapEnd = Math.min(endIndex, sectionVisibleEnd)
      if (overlapEnd <= overlapStart) {
        return
      }
      ranges.push({
        offset:
          section.absoluteRowOffset + (overlapStart - sectionVisibleStart),
        limit: overlapEnd - overlapStart,
      })
    })
  return ranges
}
