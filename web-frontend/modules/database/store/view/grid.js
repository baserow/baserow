import axios from 'axios'
import _ from 'lodash'
import BigNumber from 'bignumber.js'
import { createNewUndoRedoActionGroupId } from '@baserow/modules/database/utils/action'
import {
  createRowLifecycleContext,
  handleRowCreated,
  handleRowDeleted,
  handleRowUpdated,
  reapplyMatchFlags,
} from '@baserow/modules/database/utils/rowLifecycle'

import { uuid } from '@baserow/modules/core/utils/string'
import { clone } from '@baserow/modules/core/utils/object'
import { GroupTaskQueue } from '@baserow/modules/core/utils/queue'
import ViewService from '@baserow/modules/database/services/view'
import GridService from '@baserow/modules/database/services/view/grid'
import RowService from '@baserow/modules/database/services/row'
import {
  calculateSingleRowSearchMatches,
  extractRowMetadata,
  getFilters,
  getGroupBy,
  getOrderBy,
  canRowsBeOptimisticallyUpdatedInView,
  viewHasRulesThatCanMoveOrHideRows,
} from '@baserow/modules/database/utils/view'
import { RefreshCancelledError } from '@baserow/modules/core/errors'
import {
  prepareRowForRequest,
  prepareNewOldAndUpdateRequestValues,
  updateRowMetadataType,
  getRowMetadata,
  extractChangedFields,
  buildNewRowDefaults,
  computeRowMatchFlags,
  computeRowInsertPosition,
} from '@baserow/modules/database/utils/row'
import { getDefaultSearchModeFromEnv } from '@baserow/modules/database/utils/search'
import {
  buildLayout,
  pathKey,
  renderViewport,
  visibleGroupDepthPageInViewport,
  visibleGroupPagesInViewport,
  visibleSectionsInViewport,
} from '@baserow/modules/database/utils/gridGroupByRender'
import {
  getGroupByCollapseAllState,
  getGroupByFieldsFromActiveGroupBys,
  projectGroupByCollapseState,
  makeSectionRowsMap,
  getDefinedRowsFromSectionRows,
  forEachGroupByRow,
  getGroupByPathDepth,
  preserveGroupByRowUiState,
  findGroupByRowSection,
  getGroupByAbsoluteRangesForVisibleRange,
  getGroupByParentRowOffset,
  getGroupByRowInsertLocation,
  getMissingGroupBySectionRanges,
  collectMissingSectionRanges,
  groupPathDefaults,
  groupPathFromRow,
  isGroupByDataPageLoaded,
  placeAbsoluteRowsIntoSections,
  shouldUseGroupByDepthPages,
  updateGroupByDataPagesForPath,
  updateGroupByTreeNodesForPath,
} from '@baserow/modules/database/utils/gridGroupBy'
import {
  GRID_VIEW_MULTI_SELECT_AREA,
  GRID_VIEW_MULTI_SELECT_CHECKBOX,
  LINKED_ITEMS_LOAD_ALL,
} from '@baserow/modules/database/constants'

const ORDER_STEP = '1'
const ORDER_STEP_BEFORE = '0.00000000000000000001'
const REFRESH_ROW_DELAY_MS = 1000
// Maximum number of group-by row sections whose loaded rows are kept in memory.
// Sections are evicted least-recently-used (loaded or visible) on scroll so a long
// session stays bounded; the group tree itself is always kept so scroll geometry is
// unaffected. Generous enough that a normal viewport's working set is never evicted,
// so collapsing then re-expanding a group never refetches its rows.
const GROUP_BY_MAX_RETAINED_SECTIONS = 200
const DEFAULT_FLAT_VIEW = {
  group_bys: [],
  sortings: [],
  filters: [],
  filter_groups: [],
  filters_disabled: false,
  filter_type: 'AND',
}

function getViewOrFlatDefault(rootGetters, gridId) {
  return rootGetters['view/get'](gridId) || DEFAULT_FLAT_VIEW
}

function getNextGroupByGeneration(state) {
  return (state.groupBy?.generation || 0) + 1
}

// A group-by fetch is stale once its request was aborted, the view left group-by
// mode, or the collapse generation it was started under has been superseded. Every
// async group-by fetch re-checks this after each await before committing results.
function isGroupByRequestStale(getters, state, generation, signal = null) {
  return (
    signal?.aborted ||
    !getters.isGroupByMode ||
    (state.groupBy.generation || 0) !== generation
  )
}

function getEmptyGroupByState() {
  return {
    treeNodes: [],
    pages: {},
    absoluteRows: {},
    revision: 0,
    generation: 0,
    collapse: { mode: 'expand', paths: [] },
    collapseInitialized: false,
    sectionRows: {},
    rowLocations: {},
    sectionAccessOrder: [],
    // True while every loaded group node's row_offset is server-authoritative (no
    // optimistic mutation has shifted offsets since the last server load). Only then
    // is it safe to thread a parent's row_offset back to the server as a shortcut;
    // an optimistically-recomputed offset must never be sent.
    offsetsServerConfirmed: true,
  }
}

// Moves the given section keys to the most-recently-used end of the LRU order on a
// group-by store shape (`target` is the live `state.groupBy` or a refresh snapshot).
function touchGroupBySectionAccess(target, sectionKeys) {
  if (sectionKeys.length === 0) {
    return
  }
  const touched = new Set(sectionKeys)
  target.sectionAccessOrder = [
    ...(target.sectionAccessOrder || []).filter((key) => !touched.has(key)),
    ...sectionKeys,
  ]
}

function rowHasViewWarning(row) {
  return (
    row && (!row._.matchFilters || !row._.matchSortings || !row._.matchSearch)
  )
}

function getGroupByFieldRefsFromState(state) {
  return state.activeGroupBys.map((groupBy) => ({ id: groupBy.field }))
}

let groupByLayoutCacheKey = null
let groupByLayoutCacheValue = null

// Builds the group-by layout, memoized against the identity of every input
// buildLayout reads. The mutations replace `treeNodes`, `pages` and `collapse` by
// reference whenever they change, so the cache stays correct while letting the many
// hot-path callers (cell navigation, multi-select range walks, getAllRows,
// getRowsLength) share a single O(loaded nodes) build per state change instead of
// each rebuilding it. `sectionRows` is intentionally not a key: it does not affect
// layout geometry.
function getGroupByLayoutFromState(state) {
  const groupBy = state.groupBy
  const cacheKey = [
    groupBy.treeNodes,
    groupBy.pages,
    groupBy.collapse,
    state.rowHeight,
    state.bufferRequestSize,
    state.activeGroupBys,
  ]
  if (
    groupByLayoutCacheKey !== null &&
    cacheKey.every((part, index) => part === groupByLayoutCacheKey[index])
  ) {
    return groupByLayoutCacheValue
  }

  const pages =
    Object.keys(groupBy.pages || {}).length > 0 ? groupBy.pages : null
  const layout = buildLayout({
    nodes: groupBy.treeNodes,
    pages,
    collapse: groupBy.collapse,
    fields: getGroupByFieldRefsFromState(state),
    rowHeight: state.rowHeight,
    pageSize: state.bufferRequestSize,
  })

  groupByLayoutCacheKey = cacheKey
  groupByLayoutCacheValue = layout
  return layout
}

let groupBySectionIndexCache = null

// Derives O(1)/O(log) section lookups from the layout once per layout build, so the
// per-row navigation and multi-select getters no longer scan every layout item on
// each call. `sections` is in ascending firstGlobalRowOffset order (layout order).
function getGroupBySectionIndexFromState(state) {
  const layout = getGroupByLayoutFromState(state)
  if (groupBySectionIndexCache?.layout === layout) {
    return groupBySectionIndexCache
  }

  const fields = getGroupByFieldRefsFromState(state)
  const byKey = new Map()
  const sections = []
  for (const item of layout.items) {
    if (item.type !== 'rowSection') {
      continue
    }
    byKey.set(pathKey(item.path, fields), item)
    sections.push(item)
  }

  groupBySectionIndexCache = { layout, byKey, sections }
  return groupBySectionIndexCache
}

// Binary-searches the y-sorted, non-overlapping row sections for the one whose
// visible row range contains `rowIndex`.
function findGroupBySectionForVisibleIndex(sections, rowIndex) {
  let low = 0
  let high = sections.length - 1
  while (low <= high) {
    const mid = (low + high) >> 1
    const section = sections[mid]
    if (rowIndex < section.firstGlobalRowOffset) {
      high = mid - 1
    } else if (rowIndex >= section.firstGlobalRowOffset + section.rowCount) {
      low = mid + 1
    } else {
      return section
    }
  }
  return null
}

function getGroupByRowsInLayoutOrder(state) {
  const fields = getGroupByFieldRefsFromState(state)
  const layout = getGroupByLayoutFromState(state)
  const rows = []

  for (const item of layout.items) {
    if (item.type !== 'rowSection') {
      continue
    }
    rows.push(
      ...getDefinedRowsFromSectionRows(
        state.groupBy.sectionRows,
        pathKey(item.path, fields)
      )
    )
  }

  return rows
}

function getGroupByViewport(getters, scrollTop = getters.getScrollTop) {
  const padding = getters.getRowPadding * getters.getRowHeight
  return {
    scrollTop: Math.max(0, scrollTop - padding),
    clientHeight:
      (getters.getWindowHeight ||
        getters.getBufferRequestSize * getters.getRowHeight) +
      padding * 2,
  }
}

function getClampedGroupByScrollTop(getters, scrollTop = getters.getScrollTop) {
  const windowHeight =
    getters.getWindowHeight ||
    getters.getBufferRequestSize * getters.getRowHeight
  const maxScrollTop = Math.max(
    0,
    getters.getGroupByLayout.totalHeight - windowHeight
  )

  return Math.min(Math.max(0, scrollTop), maxScrollTop)
}

function getVisibleGroupPagesToFetch({
  state,
  getters,
  layout,
  groupByFields,
  viewport,
  seenRequests = null,
  maxGroups = null,
}) {
  const pages = []
  let remainingGroups = maxGroups

  for (const { parentPath, offset, limit } of visibleGroupPagesInViewport(
    layout,
    viewport,
    getters.getBufferRequestSize
  )) {
    if (remainingGroups !== null && remainingGroups <= 0) {
      break
    }

    const requestLimit =
      remainingGroups === null ? limit : Math.min(limit, remainingGroups)
    if (requestLimit <= 0) {
      continue
    }

    const requestKey = `${pathKey(
      parentPath,
      groupByFields
    )}:${offset}:${requestLimit}`
    if (seenRequests?.has(requestKey)) {
      continue
    }
    if (
      isGroupByDataPageLoaded(
        state.groupBy.pages,
        parentPath,
        offset,
        requestLimit,
        groupByFields
      )
    ) {
      continue
    }
    seenRequests?.add(requestKey)
    const pageRequest = { parentPath, offset, limit: requestLimit }
    // Thread the parent's known absolute row_offset so the server can skip the
    // recursive offset lookup — but only while offsets are server-authoritative, so
    // an optimistically-recomputed offset is never sent.
    if (state.groupBy.offsetsServerConfirmed) {
      const parentRowOffset = getGroupByParentRowOffset(
        state.groupBy.pages,
        parentPath,
        groupByFields
      )
      if (parentRowOffset !== undefined) {
        pageRequest.parentRowOffset = parentRowOffset
      }
    }
    pages.push(pageRequest)

    if (remainingGroups !== null) {
      remainingGroups -= requestLimit
    }
  }

  return pages
}

function getVisibleGroupDepthPageToFetch({
  layout,
  viewport,
  pageSize,
  seenRequests = null,
}) {
  const page = visibleGroupDepthPageInViewport(layout, viewport, pageSize)
  if (page === null) {
    return null
  }

  const requestKey = `${page.depth}:${page.offset}:${page.limit}`
  if (seenRequests?.has(requestKey)) {
    return null
  }

  seenRequests?.add(requestKey)
  return page
}

function findGroupByPageNodeForPath(state, path, fields) {
  const parentPath = {}
  const nodeFields = []

  for (const field of fields) {
    const key = `field_${field.id}`
    if (!(key in path)) {
      break
    }
    nodeFields.push(field)
  }

  if (nodeFields.length === 0) {
    return null
  }

  for (const field of nodeFields.slice(0, -1)) {
    parentPath[`field_${field.id}`] = path[`field_${field.id}`]
  }

  const page = state.groupBy.pages?.[pathKey(parentPath, fields)]
  const nodeKey = pathKey(path, fields)
  return Object.values(page?.nodes || {}).find(
    (node) => pathKey(node.path, fields) === nodeKey
  )
}

function getMissingAbsoluteRowRanges(absoluteRows, sections) {
  return collectMissingSectionRanges(
    sections,
    (section, position) =>
      absoluteRows?.[section.absoluteRowOffset + position] === undefined
  )
}

// Scatters a window of just-fetched rows (`rowsByOffset`, keyed by absolute offset) into
// the leaf sections it overlaps. Each section is clamped to its intersection with
// [requestOffset, requestOffset + fetchedRowCount) so placement scans only the fetched
// window, never every row of every loaded section (which would be O(total rows)).
function buildGroupBySectionPlacements({
  layout,
  rowsByOffset,
  requestOffset,
  fetchedRowCount,
  groupByFields,
  registry,
}) {
  const fetchedEnd = requestOffset + fetchedRowCount
  const sections = []
  for (const item of layout.items) {
    if (item.type !== 'rowSection') {
      continue
    }
    const sectionStart = item.absoluteRowOffset
    const sectionEnd = sectionStart + item.rowCount
    const overlapStart = Math.max(sectionStart, requestOffset)
    const overlapEnd = Math.min(sectionEnd, fetchedEnd)
    if (overlapStart >= overlapEnd) {
      continue
    }
    sections.push({
      ...item,
      sectionKey: pathKey(item.path, groupByFields),
      startPosition: overlapStart - sectionStart,
      endPosition: overlapEnd - sectionStart,
    })
  }
  return placeAbsoluteRowsIntoSections({
    absoluteRows: rowsByOffset,
    fields: groupByFields,
    registry,
    sections,
  })
}

function getGroupByRowPrefetchSections({
  state,
  pageRequests,
  groupByFields,
  maxRows,
}) {
  const sections = []
  const seen = new Set()
  let remainingRows = maxRows
  let startOffset = null
  let endOffset = null

  for (const pageRequest of pageRequests) {
    if (remainingRows <= 0) {
      break
    }

    const parentPath = pageRequest.parentPath || {}
    if (
      getGroupByPathDepth(parentPath, groupByFields) !==
      groupByFields.length - 1
    ) {
      continue
    }

    const sectionKey = pathKey(parentPath, groupByFields)
    if (sectionKey === '' || seen.has(sectionKey)) {
      continue
    }

    const node = findGroupByPageNodeForPath(state, parentPath, groupByFields)
    const rowCount = node?.row_count ?? node?.rowCount ?? 0
    const absoluteRowOffset = node?.row_offset ?? node?.rowOffset
    if (!node || rowCount <= 0 || absoluteRowOffset === undefined) {
      continue
    }

    const endPosition = Math.min(rowCount, remainingRows)
    sections.push({
      sectionKey,
      sectionPath: parentPath,
      absoluteRowOffset,
      rowCount,
      startPosition: 0,
      endPosition,
    })
    seen.add(sectionKey)
    remainingRows -= endPosition
    startOffset =
      startOffset === null
        ? absoluteRowOffset
        : Math.min(startOffset, absoluteRowOffset)
    endOffset =
      endOffset === null
        ? absoluteRowOffset + endPosition
        : Math.max(endOffset, absoluteRowOffset + endPosition)
  }

  if (startOffset === null || endOffset - startOffset > maxRows) {
    return []
  }

  return getMissingAbsoluteRowRanges(state.groupBy.absoluteRows, sections)
}

function getGroupByRowsRequestKey({
  gridId,
  offset,
  limit,
  includeFieldOptions,
  search,
  searchMode,
  publicUrl,
  publicAuthToken,
  groupBy,
  orderBy,
  filters,
}) {
  return JSON.stringify({
    gridId,
    offset,
    limit,
    includeFieldOptions,
    search,
    searchMode,
    publicUrl,
    publicAuthToken,
    groupBy,
    orderBy,
    filters,
  })
}

// Merges a fetched group-by page into a group-by store shape (`target` is either
// `state.groupBy` for the live path or an off-store snapshot for refreshActiveGroupBys).
// Keeping a single implementation prevents the live and snapshot paths from drifting.
function mergeGroupByDataPageInto(target, { data, parentPath, fields }) {
  const pageKey = pathKey(parentPath || {}, fields)
  const pages = target.pages || {}
  const existing = pages[pageKey] || {
    parentPath: parentPath || {},
    nodes: {},
    totalSiblingCount: 0,
  }
  const nodes = { ...existing.nodes }
  const groups = data.groups || []
  for (const [index, group] of groups.entries()) {
    const siblingIndex = group.sibling_index ?? data.offset + index
    nodes[siblingIndex] = group
  }
  target.pages = {
    ...pages,
    [pageKey]: {
      parentPath: parentPath || {},
      nodes,
      totalSiblingCount: data.group_count ?? 0,
    },
  }
  target.treeNodes = Object.values(
    target.pages[pathKey({}, fields)]?.nodes || {}
  ).sort((a, b) => (a.sibling_index ?? 0) - (b.sibling_index ?? 0))
}

function getGroupBySnapshotLayout(snapshot, activeGroupBys, fields, state) {
  const groupByFields = getGroupByFieldsFromActiveGroupBys(
    activeGroupBys,
    fields
  )
  const pages =
    Object.keys(snapshot.pages || {}).length > 0 ? snapshot.pages : null
  return buildLayout({
    nodes: snapshot.treeNodes,
    pages,
    collapse: snapshot.collapse,
    fields: groupByFields,
    rowHeight: state.rowHeight,
    pageSize: state.bufferRequestSize,
  })
}

// Reindexes section row positions on a group-by store shape (`target` is the live
// `state.groupBy` or an off-store snapshot). Shared so the snapshot path keeps the
// same authoritative-rowLocations invariant guard as the live path.
function reindexGroupBySectionPositionsInto(target, sectionKey) {
  const rows = target.sectionRows[sectionKey] || []
  rows.forEach((row, position) => {
    if (!row) {
      return
    }
    const location = target.rowLocations[row.id]
    if (location) {
      location.position = position
    } else if (import.meta.env.MODE !== 'production') {
      // Invariant: every row materialized in sectionRows must have a rowLocations
      // entry (rowLocations is authoritative). Drift would silently break getRow, so
      // surface it loudly in non-production builds instead of skipping the row.
      console.error(
        `Grid group-by invariant violated: row ${row.id} in section ` +
          `"${sectionKey}" has no rowLocations entry.`
      )
    }
  })
}

function setGroupBySectionRowsInto(
  target,
  state,
  { sectionKey, rows, startPosition = 0 }
) {
  const current = target.sectionRows[sectionKey]
    ? [...target.sectionRows[sectionKey]]
    : []

  rows.forEach((row, index) => {
    const position = startPosition + index
    current[position] = preserveGroupByRowUiState(
      row,
      getGroupByRowStateById(state, row.id)
    )
    target.rowLocations[row.id] = {
      sectionKey,
      position,
    }
  })

  target.sectionRows = {
    ...target.sectionRows,
    [sectionKey]: current,
  }
  touchGroupBySectionAccess(target, [sectionKey])
  reindexGroupBySectionPositionsInto(target, sectionKey)
}

function placeLoadedGroupByRowsInViewport({
  commit,
  getters,
  state,
  registry,
  fields,
  layout = null,
  scrollTop = getters.getScrollTop,
}) {
  if (Object.keys(state.groupBy.absoluteRows || {}).length === 0) {
    return
  }

  const groupByFields = getGroupByFieldsFromActiveGroupBys(
    getters.getActiveGroupBys,
    fields
  )
  const sections = visibleSectionsInViewport(
    layout || getters.getGroupByLayout,
    getGroupByViewport(getters, scrollTop),
    groupByFields,
    getters.getRowHeight
  )

  placeAbsoluteRowsIntoSections({
    absoluteRows: state.groupBy.absoluteRows,
    fields: groupByFields,
    registry,
    sections,
    // Only restore rows into positions that aren't already materialized. Overwriting a
    // loaded position would clobber an optimistic move with stale cached data.
    isPositionLoaded: (sectionKey, position) =>
      state.groupBy.sectionRows[sectionKey]?.[position] !== undefined,
  }).forEach((placement) => {
    commit('SET_GROUP_BY_SECTION_ROWS', placement)
  })
}

function getGroupByVisibleIndexForLocation(state, location) {
  if (!location) {
    return -1
  }

  const section = getGroupBySectionIndexFromState(state).byKey.get(
    location.sectionKey
  )
  if (!section) {
    return -1
  }

  return section.firstGlobalRowOffset + location.position
}

function getGroupByRowIdByVisibleIndex(state, rowIndex) {
  const { sections } = getGroupBySectionIndexFromState(state)
  const section = findGroupBySectionForVisibleIndex(sections, rowIndex)
  if (!section) {
    return -1
  }

  const fields = getGroupByFieldRefsFromState(state)
  const row =
    state.groupBy.sectionRows[pathKey(section.path, fields)]?.[
      rowIndex - section.firstGlobalRowOffset
    ]
  return row?.id ?? -1
}

function reindexGroupBySectionPositions(state, sectionKey) {
  reindexGroupBySectionPositionsInto(state.groupBy, sectionKey)
}

/**
 * Drops the absolute-offset row cache after an optimistic reposition. A move shifts the
 * absolute offsets of the moved row (and the rows it passed) but doesn't re-key
 * `absoluteRows`, so it would otherwise restore an evicted section at stale offsets.
 * Count-changing ops already clear it via `UPDATE_GROUP_BY_TREE_PATH_COUNT`; this also
 * covers same-section moves, which don't change any group's count.
 */
function invalidateGroupByAbsoluteRows(state) {
  state.groupBy.absoluteRows = {}
}

function getGroupByRowStateById(state, rowId) {
  const location = state.groupBy.rowLocations[rowId]
  if (!location) {
    return null
  }
  return state.groupBy.sectionRows[location.sectionKey]?.[location.position]
}

/**
 * Resolves the group-by fields and the section/path where `row` should be inserted,
 * bundling the boilerplate shared by every grouped insert site: map the active
 * group-bys to fields, then compute the insert location from the current layout and
 * the materialized section rows.
 */
function resolveGroupByInsertLocation(
  { getters, state, registry },
  { row, view, fields }
) {
  const groupByFields = getGroupByFieldsFromActiveGroupBys(
    getters.getActiveGroupBys,
    fields
  )
  const location = getGroupByRowInsertLocation({
    row,
    view,
    fields,
    registry,
    groupByFields,
    sectionRows: state.groupBy.sectionRows,
  })
  return { groupByFields, location }
}

/**
 * Populates fresh rows from text (or JSON) data. The number of returned rows will match
 * the number of rows from tsvData list.
 *
 * @param tsvData a list of values in text format
 * @param jsonData (optional) a list of values from json. Should match in number with
 *  tsvData
 * @param fieldsInOrder a list of fields used
 * @param registry
 * @param fromRows (optional) a list of existing rows which will be used to pre-populate
 * @param forUpdate (optional) if true, the values will be prepared to be used for an update
 * request. If false, the values won't be prepared and will contain the rich values prepared
 * for paste.
 *  rows
 * @returns {*[]}
 */
function populateRows({
  tsvData,
  jsonData,
  fieldsInOrder,
  registry,
  fromRows,
  forUpdate = true,
}) {
  const newRows = []

  // Prepare the values for update and update the row objects.
  tsvData.forEach((tsvRow, rowIndex) => {
    const oldRow = fromRows ? fromRows[rowIndex] : {}
    const row = {}
    if (oldRow) {
      row.id = oldRow.id
    }

    fieldsInOrder.forEach((field, fieldIndex) => {
      const fieldType = registry.get('field', field.type)
      // We can't pre-filter because we need the correct filter index.
      if (!fieldType.canWriteFieldValues(field)) {
        return
      }

      const fieldId = `field_${field.id}`
      const textValue = tsvRow[fieldIndex]
      const jsonValue = jsonData != null ? jsonData[rowIndex][fieldIndex] : null
      const preparedValue = fieldType.prepareValueForPaste(
        field,
        textValue,
        jsonValue
      )
      if (forUpdate) {
        row[fieldId] = fieldType.prepareValueForUpdate(field, preparedValue)
      } else {
        row[fieldId] = preparedValue
      }
    })
    newRows.push(row)
  })

  return newRows
}

export function populateRow(row, metadata = {}, fullyLoaded = true) {
  row._ = {
    metadata: getRowMetadata(row, metadata),
    persistentId: uuid(),
    loading: false,
    hover: false,
    selectedBy: [],
    matchFilters: true,
    matchSortings: true,
    // Whether the row should be displayed based on the current activeSearchTerm term.
    matchSearch: true,
    // Contains the specific field ids which match the activeSearchTerm term.
    // Could be empty even when matchSearch is true when there is no
    // activeSearchTerm term applied.
    fieldSearchMatches: [],
    // Keeping the selected state with the row has the best performance when navigating
    // between cells.
    selected: false,
    selectedFieldId: -1,
    // When loaded together with other rows, some fields might not be fetched
    // completely. This flag indicates that the row has been fully loaded, including all
    // the linked items and array values.
    fetching: false,
    fullyLoaded,
  }

  return row
}

const updatePositionFn = {
  previous: (rowIndex, fieldIndex) => {
    return [rowIndex, fieldIndex - 1]
  },
  next: (rowIndex, fieldIndex) => {
    return [rowIndex, fieldIndex + 1]
  },
  above: (rowIndex, fieldIndex) => {
    return [rowIndex - 1, fieldIndex]
  },
  below: (rowIndex, fieldIndex) => {
    return [rowIndex + 1, fieldIndex]
  },
}

function getPendingOperationKey(fieldId, rowId) {
  return `${fieldId}-${rowId}`
}

export const state = () => ({
  // Indicates if multiple cell selection is active
  multiSelectActive: false,
  // Indicates if the user is clicking and holding the mouse over a cell
  multiSelectHolding: false,
  // Indicates the current selection type: 'checkbox', 'area', or null
  selectionType: null,
  /**
   * The indexes for head and tail cells in a multi-select grid.
   * Multi-Select works by tracking four different indexes, these are:
   *   - The field and row index for the first cell selected, known as the head.
   *   - The field and row index for the last cell selected, known as the tail.
   * All the cells between the head and tail cells are later also calculated as selected.
   */
  multiSelectHeadRowIndex: -1,
  multiSelectHeadFieldIndex: -1,
  multiSelectTailRowIndex: -1,
  multiSelectTailFieldIndex: -1,
  // Keep the original row and field index to remember where the selection began
  multiSelectStartRowIndex: -1,
  multiSelectStartFieldIndex: -1,
  // The last used grid id.
  lastGridId: -1,
  // If true, ad hoc filtering is used instead of persistent one
  adhocFiltering: false,
  // If true, ad hoc sorting is used
  adhocSorting: false,
  // Contains the custom field options per view. Things like the field width are
  // stored here.
  fieldOptions: {},
  // Contains the buffered rows that we keep in memory. Depending on the
  // scrollOffset rows will be added or removed from this buffer. Most of the times,
  // it will contain 3 times the bufferRequestSize in rows.
  rows: [],
  // The total amount of rows in the table.
  count: 0,
  // The height of a single row.
  rowHeight: 33,
  // The distance to the top in pixels the visible rows should have.
  rowsTop: 0,
  // The amount of rows that must be visible above and under the middle row.
  rowPadding: 16,
  // The amount of rows that will be requested per request.
  bufferRequestSize: 40,
  // The start index of the buffer in the whole table.
  bufferStartIndex: 0,
  // The limit of the buffer measured from the start index in the whole table.
  bufferLimit: 0,
  // The start index of the visible rows of the rows in the buffer.
  rowsStartIndex: 0,
  // The end index of the visible rows of the rows buffer.
  rowsEndIndex: 0,
  // The last scrollTop when the visibleByScrollTop was called.
  scrollTop: 0,
  // The height of the window where the rows are displayed in.
  windowHeight: 0,
  // Indicates if the user is hovering over the add row button.
  addRowHover: false,
  // A user provided optional search term which can be used to filter down rows.
  activeSearchTerm: '',
  // If true then the activeSearchTerm will be sent to the server to filter rows
  // entirely out. When false no server filter will be applied and rows which do not
  // have any matching cells will still be displayed.
  hideRowsNotMatchingSearch: true,
  fieldAggregationData: {},
  activeGroupBys: [],
  groupBy: getEmptyGroupByState(),
  // Contains a fieldId and rowId string pair that looks like `{fieldId}-{rowId}`. If
  // in the array, then that cell is a loading state. This is for example used for
  // fields that use a background worker to compute the value like the AI field.
  pendingFieldOps: {},
  checkboxSelectedRows: [], // Array of row IDs selected by checkboxes
})

export const mutations = {
  CLEAR_ROWS(state) {
    state.fieldOptions = {}
    state.count = 0
    state.rows = []
    state.rowsTop = 0
    state.bufferStartIndex = 0
    state.bufferLimit = 0
    state.rowsStartIndex = 0
    state.rowsEndIndex = 0
    state.scrollTop = 0
    state.addRowHover = false
    state.activeSearchTerm = ''
    state.hideRowsNotMatchingSearch = true
    state.pendingFieldOps = {}
    state.checkboxSelectedRows = []
    state.selectionType = null
    state.groupBy = {
      ...getEmptyGroupByState(),
      generation: getNextGroupByGeneration(state),
    }
  },
  SET_ACTIVE_GROUP_BYS(state, groupBys) {
    state.activeGroupBys = groupBys
  },
  INVALIDATE_GROUP_BY_REQUESTS(state) {
    state.groupBy.generation = getNextGroupByGeneration(state)
  },
  APPLY_GROUP_BY_STATE(state, { activeGroupBys, groupBy, count = null }) {
    state.activeGroupBys = activeGroupBys
    state.groupBy = groupBy
    if (typeof count === 'number') {
      state.count = count
    }
  },
  RESET_GROUP_BY_DATA(state) {
    const generation = getNextGroupByGeneration(state)
    const collapse = state.groupBy.collapse
    const collapseInitialized = state.groupBy.collapseInitialized
    state.groupBy = {
      ...getEmptyGroupByState(),
      generation,
      collapse,
      collapseInitialized,
    }
  },
  SET_GROUP_BY_DATA_PAGE(state, payload) {
    mergeGroupByDataPageInto(state.groupBy, payload)
  },
  SET_GROUP_BY_COLLAPSE(state, collapse) {
    state.groupBy.collapse = collapse
    state.groupBy.collapseInitialized = true
    state.groupBy.generation = getNextGroupByGeneration(state)
  },
  TOGGLE_GROUP_BY_COLLAPSE_PATH(state, { path, fields }) {
    const key = pathKey(path, fields)
    const existingIndex = state.groupBy.collapse.paths.findIndex(
      (p) => pathKey(p, fields) === key
    )
    const paths = [...state.groupBy.collapse.paths]
    if (existingIndex === -1) {
      paths.push(path)
    } else {
      paths.splice(existingIndex, 1)
    }
    state.groupBy.collapse = { ...state.groupBy.collapse, paths }
    state.groupBy.collapseInitialized = true
    state.groupBy.generation = getNextGroupByGeneration(state)
  },
  SET_GROUP_BY_SECTION_ROWS(state, payload) {
    setGroupBySectionRowsInto(state.groupBy, state, payload)
  },
  INSERT_ROW_AT_LOCATION(state, { sectionKey, position, row }) {
    const current = state.groupBy.sectionRows[sectionKey]
      ? [...state.groupBy.sectionRows[sectionKey]]
      : []
    current.splice(position, 0, row)
    state.groupBy.sectionRows = {
      ...state.groupBy.sectionRows,
      [sectionKey]: current,
    }
    state.groupBy.rowLocations[row.id] = { sectionKey, position }
    reindexGroupBySectionPositions(state, sectionKey)
    invalidateGroupByAbsoluteRows(state)
  },
  REMOVE_ROW_AT_LOCATION(state, { sectionKey, position, rowId }) {
    const current = state.groupBy.sectionRows[sectionKey]
      ? [...state.groupBy.sectionRows[sectionKey]]
      : []
    current.splice(position, 1)
    state.groupBy.sectionRows = {
      ...state.groupBy.sectionRows,
      [sectionKey]: current,
    }
    if (rowId !== undefined) {
      delete state.groupBy.rowLocations[rowId]
    }
    reindexGroupBySectionPositions(state, sectionKey)
    invalidateGroupByAbsoluteRows(state)
  },
  CLEAR_GROUP_BY_SECTION_ROWS(state) {
    state.groupBy.sectionRows = {}
    state.groupBy.rowLocations = {}
    state.groupBy.absoluteRows = {}
    state.groupBy.sectionAccessOrder = []
  },
  TOUCH_GROUP_BY_SECTIONS(state, { sectionKeys }) {
    touchGroupBySectionAccess(state.groupBy, sectionKeys)
  },
  EVICT_LRU_GROUP_BY_SECTIONS(state, { cap }) {
    const order = state.groupBy.sectionAccessOrder || []
    if (order.length <= cap) {
      return
    }
    const evicted = new Set(order.slice(0, order.length - cap))
    // Drop the evicted sections' rows and their location entries (rowLocations is
    // authoritative); the group tree is kept so scroll geometry is unaffected and the
    // rows are re-fetched if their section scrolls back into view.
    for (const sectionKey of evicted) {
      const rows = state.groupBy.sectionRows[sectionKey]
      if (!rows) {
        continue
      }
      for (const row of rows) {
        if (row) {
          delete state.groupBy.rowLocations[row.id]
        }
      }
    }
    state.groupBy.sectionRows = Object.fromEntries(
      Object.entries(state.groupBy.sectionRows).filter(
        ([key]) => !evicted.has(key)
      )
    )
    state.groupBy.sectionAccessOrder = order.filter((key) => !evicted.has(key))
  },
  SET_GROUP_BY_ABSOLUTE_ROWS(state, rowsByOffset) {
    state.groupBy.absoluteRows = {
      ...state.groupBy.absoluteRows,
      ...rowsByOffset,
    }
  },
  UPDATE_GROUP_BY_TREE_PATH_COUNT(state, { path, fields, delta, registry }) {
    state.groupBy.revision = (state.groupBy.revision || 0) + 1
    state.groupBy.absoluteRows = {}
    // Offsets are now locally recomputed and may diverge from the server until the
    // next full refresh, so stop threading parent_row_offset back to the server.
    state.groupBy.offsetsServerConfirmed = false
    const hasSparsePages = Object.keys(state.groupBy.pages || {}).length > 0
    const groupBys = state.activeGroupBys || []
    state.groupBy.treeNodes = updateGroupByTreeNodesForPath(
      state.groupBy.treeNodes,
      path,
      fields,
      delta,
      groupBys,
      registry,
      hasSparsePages
    )
    if (hasSparsePages) {
      state.groupBy.pages = updateGroupByDataPagesForPath(
        state.groupBy.pages,
        path,
        fields,
        delta,
        groupBys,
        registry
      )
    }
  },
  SET_SEARCH(state, { activeSearchTerm, hideRowsNotMatchingSearch }) {
    state.activeSearchTerm = activeSearchTerm.trim()
    state.hideRowsNotMatchingSearch = hideRowsNotMatchingSearch
  },
  SET_LAST_GRID_ID(state, gridId) {
    state.lastGridId = gridId
  },
  SET_ADHOC_FILTERING(state, adhocFiltering) {
    state.adhocFiltering = adhocFiltering
  },
  SET_ADHOC_SORTING(state, adhocSorting) {
    state.adhocSorting = adhocSorting
  },
  SET_SCROLL_TOP(state, scrollTop) {
    state.scrollTop = scrollTop
  },
  SET_WINDOW_HEIGHT(state, value) {
    state.windowHeight = value
  },
  SET_ROW_PADDING(state, value) {
    state.rowPadding = value
  },
  SET_BUFFER_START_INDEX(state, value) {
    state.bufferStartIndex = value
  },
  SET_BUFFER_LIMIT(state, value) {
    state.bufferLimit = value
  },
  SET_COUNT(state, value) {
    state.count = value
  },
  SET_ROWS_INDEX(state, { startIndex, endIndex, top }) {
    state.rowsStartIndex = startIndex
    state.rowsEndIndex = endIndex
    state.rowsTop = top
  },
  SET_ADD_ROW_HOVER(state, value) {
    state.addRowHover = value
  },
  /**
   * It will add and remove rows to the state based on the provided values. For example
   * if prependToRows is a positive number that amount of the provided rows will be
   * added to the state. If that number is negative that amount will be removed from
   * the state. Same goes for the appendToRows, only then it will be appended.
   */
  ADD_ROWS(
    state,
    { rows, prependToRows, appendToRows, count, bufferStartIndex, bufferLimit }
  ) {
    if (count !== undefined) {
      state.count = count
    }
    state.bufferStartIndex = bufferStartIndex
    state.bufferLimit = bufferLimit

    if (prependToRows > 0) {
      state.rows = [...rows.slice(0, prependToRows), ...state.rows]
    }
    if (appendToRows > 0) {
      state.rows.push(...rows.slice(0, appendToRows))
    }

    if (prependToRows < 0) {
      state.rows = state.rows.splice(Math.abs(prependToRows))
    }
    if (appendToRows < 0) {
      state.rows = state.rows.splice(
        0,
        state.rows.length - Math.abs(appendToRows)
      )
    }
    rows.forEach((row) => {
      if (state.checkboxSelectedRows.includes(row.id)) {
        if (!row._.selectedBy) {
          row._.selectedBy = []
        }
        if (!row._.selectedBy.includes(0)) {
          row._.selectedBy.push(0)
        }
      }
    })
  },
  REPLACE_ALL_FIELD_OPTIONS(state, fieldOptions) {
    state.fieldOptions = fieldOptions
  },
  UPDATE_ALL_FIELD_OPTIONS(state, fieldOptions) {
    state.fieldOptions = _.merge({}, state.fieldOptions, fieldOptions)
  },
  /**
   * Only adds the new field options and removes the deleted ones.
   * Existing field options will be modified only if they are important
   * for public view sharing.
   */
  REPLACE_PUBLIC_FIELD_OPTIONS(state, fieldOptions) {
    // Add the missing field options or modify existing ones
    Object.keys(fieldOptions).forEach((key) => {
      const exists = Object.prototype.hasOwnProperty.call(
        state.fieldOptions,
        key
      )
      if (exists) {
        const propsToUpdate = ['aggregation_raw_type', 'aggregation_type']
        const singleFieldOptions = state.fieldOptions[key]
        Object.keys(singleFieldOptions).forEach((optionKey) => {
          if (propsToUpdate.includes(optionKey)) {
            state.fieldOptions[key][optionKey] = fieldOptions[key][optionKey]
          }
        })
      } else {
        state.fieldOptions[key] = fieldOptions[key]
      }
    })

    // Remove the deleted ones.
    Object.keys(state.fieldOptions).forEach((key) => {
      const exists = Object.prototype.hasOwnProperty.call(fieldOptions, key)
      if (!exists) {
        delete state.fieldOptions[key]
      }
    })
  },
  UPDATE_FIELD_OPTIONS_OF_FIELD(state, { fieldId, values }) {
    if (Object.prototype.hasOwnProperty.call(state.fieldOptions, fieldId)) {
      Object.assign(state.fieldOptions[fieldId], values)
    } else {
      state.fieldOptions = Object.assign({}, state.fieldOptions, {
        [fieldId]: values,
      })
    }
  },
  DELETE_FIELD_OPTIONS(state, fieldId) {
    if (Object.prototype.hasOwnProperty.call(state.fieldOptions, fieldId)) {
      delete state.fieldOptions[fieldId]
    }
  },
  SET_ROW_HOVER(state, { row, value }) {
    row._.hover = value
  },
  SET_ROW_LOADING(state, { row, value }) {
    row._.loading = value
  },
  SET_ROW_SEARCH_MATCHES(state, { row, matchSearch, fieldSearchMatches }) {
    row._.fieldSearchMatches.slice(0).forEach((value) => {
      if (!fieldSearchMatches.has(value)) {
        const index = row._.fieldSearchMatches.indexOf(value)
        row._.fieldSearchMatches.splice(index, 1)
      }
    })
    fieldSearchMatches.forEach((value) => {
      if (!row._.fieldSearchMatches.includes(value)) {
        row._.fieldSearchMatches.push(value)
      }
    })
    row._.matchSearch = matchSearch
  },
  SET_ROW_MATCH_FILTERS(state, { row, value }) {
    row._.matchFilters = value
  },
  SET_ROW_MATCH_SORTINGS(state, { row, value }) {
    row._.matchSortings = value
  },
  ADD_ROW_SELECTED_BY(state, { row, fieldId }) {
    if (!row._.selectedBy.includes(fieldId)) {
      row._.selectedBy.push(fieldId)
    }
  },
  REMOVE_ROW_SELECTED_BY(state, { row, fieldId }) {
    const index = row._.selectedBy.indexOf(fieldId)
    if (index > -1) {
      row._.selectedBy.splice(index, 1)
    }
  },
  SET_SELECTED_CELL(state, { rowId, fieldId }) {
    const visitRow = (row) => {
      if (row._.selected) {
        row._.selected = false
        row._.selectedFieldId = -1
      }
      if (row.id === rowId) {
        row._.selected = true
        row._.selectedFieldId = fieldId
      }
    }

    if (state.activeGroupBys.length > 0) {
      forEachGroupByRow(state.groupBy.sectionRows, visitRow)
    } else {
      state.rows.forEach(visitRow)
    }
  },
  SET_MULTISELECT_START_ROW_INDEX(state, value) {
    state.multiSelectStartRowIndex = value
  },
  SET_MULTISELECT_START_FIELD_INDEX(state, value) {
    state.multiSelectStartFieldIndex = value
  },
  UPDATE_MULTISELECT(state, { position, rowIndex, fieldIndex }) {
    if (position === 'head') {
      state.multiSelectHeadRowIndex = rowIndex
      state.multiSelectHeadFieldIndex = fieldIndex
    } else if (position === 'tail') {
      state.multiSelectTailRowIndex = rowIndex
      state.multiSelectTailFieldIndex = fieldIndex
    }
  },
  SET_MULTISELECT_HOLDING(state, value) {
    state.multiSelectHolding = value
  },
  SET_MULTISELECT_ACTIVE(state, value) {
    state.multiSelectActive = value
  },
  CLEAR_AREA_SELECTION(state) {
    state.multiSelectHolding = false
    state.multiSelectHeadRowIndex = -1
    state.multiSelectHeadFieldIndex = -1
    state.multiSelectTailRowIndex = -1
    state.multiSelectTailFieldIndex = -1
  },
  CLEAR_AREA_START_SELECTION(state) {
    state.multiSelectStartRowIndex = -1
    state.multiSelectStartFieldIndex = -1
  },
  CLEAR_CHECKBOX_SELECTION(state) {
    state.checkboxSelectedRows = []
  },
  ADD_FIELD_TO_ROWS_IN_BUFFER(state, { field, value }) {
    const name = `field_${field.id}`
    // We have to replace all the rows by using the map function to make it
    // reactive and update immediately. If we don't do this, the value in the
    // field components of the grid and modal don't always have the correct value
    // binding.
    state.rows = state.rows.map((row) => {
      if (!Object.prototype.hasOwnProperty.call(row, name)) {
        row[`field_${field.id}`] = value
      }
      return { ...row }
    })
  },
  DECREASE_ORDERS_IN_BUFFER_LOWER_THAN(state, existingOrder) {
    const min = new BigNumber(existingOrder).integerValue(BigNumber.ROUND_FLOOR)
    const max = new BigNumber(existingOrder)

    // Decrease all the orders that have already have been inserted before the same
    // row.
    state.rows.forEach((row) => {
      const order = new BigNumber(row.order)
      if (order.isGreaterThan(min) && order.isLessThanOrEqualTo(max)) {
        row.order = order.minus(new BigNumber(ORDER_STEP_BEFORE)).toString()
      }
    })
  },
  INSERT_NEW_ROWS_IN_BUFFER_AT_INDEX(state, { rows, index }) {
    if (rows.length === 0) {
      return
    }

    const potentialNewBufferLimit = state.bufferLimit + rows.length
    const maximumBufferLimit = state.bufferRequestSize * 3

    state.count += rows.length
    state.bufferLimit =
      potentialNewBufferLimit > maximumBufferLimit
        ? maximumBufferLimit
        : potentialNewBufferLimit

    // Insert the new rows
    state.rows.splice(index, 0, ...rows)

    // We might have too many rows inserted now
    state.rows = state.rows.slice(0, state.bufferLimit)
  },
  INSERT_EXISTING_ROW_IN_BUFFER_AT_INDEX(state, { row, index }) {
    state.rows.splice(index, 0, row)
  },
  MOVE_EXISTING_ROW_IN_BUFFER(state, { row, index }) {
    const oldIndex = state.rows.findIndex((item) => item.id === row.id)
    if (oldIndex !== -1) {
      state.rows.splice(index, 0, state.rows.splice(oldIndex, 1)[0])
    }
  },
  SET_ROW_FETCHING(state, { row, value }) {
    let existingRowState = state.rows.find((item) => item.id === row.id)
    if (!existingRowState && state.activeGroupBys.length > 0) {
      const location = state.groupBy.rowLocations[row.id]
      existingRowState =
        location && state.groupBy.sectionRows[location.sectionKey]
          ? state.groupBy.sectionRows[location.sectionKey][location.position]
          : undefined
    }
    if (existingRowState) {
      existingRowState._.fetching = value
      existingRowState._.fullyLoaded = !value
    }
  },
  UPDATE_ROW_IN_BUFFER(state, { row, values, metadata = false }) {
    let existingRowState = state.rows.find((item) => item.id === row.id)
    if (!existingRowState && state.activeGroupBys.length > 0) {
      const location = state.groupBy.rowLocations[row.id]
      existingRowState =
        location && state.groupBy.sectionRows[location.sectionKey]
          ? state.groupBy.sectionRows[location.sectionKey][location.position]
          : undefined
    }
    if (existingRowState) {
      Object.assign(existingRowState, values)
      if (metadata) {
        existingRowState._.metadata = metadata
      }
    }
  },
  UPDATE_ROW_VALUES(state, { row, values }) {
    Object.assign(row, values)
  },
  UPDATE_ROW_FIELD_VALUE(state, { row, field, value }) {
    row[`field_${field.id}`] = value
  },
  UPDATE_ROW_METADATA(state, { row, rowMetadataType, updateFunction }) {
    updateRowMetadataType(row, rowMetadataType, updateFunction)
  },
  FINALIZE_ROWS_IN_BUFFER(state, { oldRows, newRows, fields }) {
    if (state.activeGroupBys.length > 0) {
      for (let i = 0; i < oldRows.length; i++) {
        const oldRow = oldRows[i]
        const newRow = newRows[i]
        const oldRowId = oldRow.id
        const location = state.groupBy.rowLocations[oldRowId]
        if (!location) {
          continue
        }

        const selectedIndex = state.checkboxSelectedRows.indexOf(oldRow.id)
        if (selectedIndex !== -1) {
          state.checkboxSelectedRows[selectedIndex] = newRow.id
        }

        const existingRowState =
          state.groupBy.sectionRows[location.sectionKey]?.[location.position]
        if (!existingRowState) {
          continue
        }

        existingRowState.id = newRow.id
        existingRowState.order = new BigNumber(newRow.order)
        existingRowState._.loading = false
        Object.keys(newRow).forEach((key) => {
          if (fields.includes(key)) {
            existingRowState[key] = newRow[key]
          }
        })
        delete state.groupBy.rowLocations[oldRowId]
        state.groupBy.rowLocations[newRow.id] = location
      }
      return
    }

    const stateRowsCopy = { ...state.rows }

    for (let i = 0; i < oldRows.length; i++) {
      const oldRow = oldRows[i]
      const newRow = newRows[i]

      const index = state.rows.findIndex((row) => row.id === oldRow.id)

      if (index === -1) {
        continue
      }

      // When row is added, we set UUID as temporary id. Once backend
      // returns the row with proper ID we need to make sure that the
      // checkbox selection is properly updated.
      const selectedIndex = state.checkboxSelectedRows.indexOf(oldRow.id)
      if (selectedIndex !== -1) {
        state.checkboxSelectedRows[selectedIndex] = newRow.id
      }

      stateRowsCopy[index].id = newRow.id
      stateRowsCopy[index].order = new BigNumber(newRow.order)
      stateRowsCopy[index]._.loading = false
      Object.keys(newRow).forEach((key) => {
        if (fields.includes(key)) {
          stateRowsCopy[index][key] = newRow[key]
        }
      })
    }

    this.state.rows = stateRowsCopy
  },
  /**
   * Deletes a row of which we are sure that it is in the buffer right now.
   */
  DELETE_ROW_IN_BUFFER(state, row) {
    if (state.activeGroupBys.length > 0) {
      const location = state.groupBy.rowLocations[row.id]
      if (location) {
        const current = [
          ...(state.groupBy.sectionRows[location.sectionKey] || []),
        ]
        current.splice(location.position, 1)
        state.groupBy.sectionRows = {
          ...state.groupBy.sectionRows,
          [location.sectionKey]: current,
        }
        delete state.groupBy.rowLocations[row.id]
        reindexGroupBySectionPositions(state, location.sectionKey)
        state.count--
      }
      return
    }
    const index = state.rows.findIndex((item) => item.id === row.id)
    if (index !== -1) {
      state.count--
      state.bufferLimit--
      state.rows.splice(index, 1)
    }
  },
  /**
   * Deletes a row from the buffer without updating the buffer limit and count.
   */
  DELETE_ROW_IN_BUFFER_WITHOUT_UPDATE(state, row) {
    if (state.activeGroupBys.length > 0) {
      const location = state.groupBy.rowLocations[row.id]
      if (location) {
        const current = [
          ...(state.groupBy.sectionRows[location.sectionKey] || []),
        ]
        current.splice(location.position, 1)
        state.groupBy.sectionRows = {
          ...state.groupBy.sectionRows,
          [location.sectionKey]: current,
        }
        delete state.groupBy.rowLocations[row.id]
        reindexGroupBySectionPositions(state, location.sectionKey)
      }
      return
    }
    const index = state.rows.findIndex((item) => item.id === row.id)
    if (index !== -1) {
      state.rows.splice(index, 1)
    }
  },
  SET_FIELD_AGGREGATION_DATA(state, { fieldId, value: newValue }) {
    const current = state.fieldAggregationData[fieldId] || {
      loading: false,
    }

    state.fieldAggregationData = {
      ...state.fieldAggregationData,
      [fieldId]: { ...current, value: newValue },
    }
  },
  SET_FIELD_AGGREGATION_DATA_LOADING(
    state,
    { fieldId, value: newLoadingValue }
  ) {
    const current = state.fieldAggregationData[fieldId] || {
      value: null,
    }

    state.fieldAggregationData = {
      ...state.fieldAggregationData,
      [fieldId]: { ...current, loading: newLoadingValue },
    }
  },
  SET_PENDING_FIELD_OPERATIONS(state, { fieldId, rowIds, value }) {
    const addKey = (fieldId, rowId) => {
      const key = getPendingOperationKey(fieldId, rowId)
      state.pendingFieldOps[key] = [fieldId, rowId]
    }
    const deleteKey = (fieldId, rowId) => {
      const key = getPendingOperationKey(fieldId, rowId)
      delete state.pendingFieldOps[key]
    }
    const operation = value ? addKey : deleteKey

    rowIds.forEach((rowId) => operation(fieldId, rowId))
  },
  CLEAR_PENDING_FIELD_OPERATIONS(state, { fieldIds, rowId }) {
    fieldIds.forEach((fieldId) => {
      const key = getPendingOperationKey(fieldId, rowId)
      delete state.pendingFieldOps[key]
    })
  },
  CLEAR_ALL_PENDING_FIELD_OPERATIONS_FOR_FIELD(state, { fieldId }) {
    const keysToDelete = Object.keys(state.pendingFieldOps).filter(
      (key) => state.pendingFieldOps[key][0] === fieldId
    )
    keysToDelete.forEach((key) => {
      delete state.pendingFieldOps[key]
    })
  },
  UPDATE_ROW_HEIGHT(state, value) {
    state.rowHeight = value
  },
  ADD_CHECKBOX_SELECTED_ROW(state, rowId) {
    if (!state.checkboxSelectedRows.includes(rowId)) {
      state.checkboxSelectedRows.push(rowId)
    }
  },
  REMOVE_CHECKBOX_SELECTED_ROW(state, rowId) {
    const index = state.checkboxSelectedRows.indexOf(rowId)
    if (index > -1) {
      state.checkboxSelectedRows.splice(index, 1)
    }
  },
  CLEAR_CHECKBOX_SELECTED_ROWS(state) {
    state.checkboxSelectedRows = []
  },
  SET_SELECTION_TYPE(state, type) {
    state.selectionType = type
  },
  SET_MULTISELECT_HEAD_ROW_INDEX(state, value) {
    state.multiSelectHeadRowIndex = value
  },
  SET_MULTISELECT_HEAD_FIELD_INDEX(state, value) {
    state.multiSelectHeadFieldIndex = value
  },
  SET_MULTISELECT_TAIL_ROW_INDEX(state, value) {
    state.multiSelectTailRowIndex = value
  },
  SET_MULTISELECT_TAIL_FIELD_INDEX(state, value) {
    state.multiSelectTailFieldIndex = value
  },
}

// Contains the info needed for the delayed scroll top action.
const fireScrollTop = {
  last: Date.now(),
  timeout: null,
  processing: false,
  distance: 0,
}

const createAndUpdateRowQueue = new GroupTaskQueue()

// Contains the last row request to be able to cancel it.
let lastRequest = null
let lastRequestOffset = null
let lastRequestLimit = null
let lastRefreshRequest = null
let lastRefreshRequestController = null
let lastQueryController = null
let lastGroupByScrollRequest = null
let lastGroupByScrollRequestKey = null
let lastGroupByScrollQueryController = null
const activeGroupByRowsRequests = new Map()

// We want to cancel previous aggregation request before creating a new one.
const lastAggregationRequest = { request: null, controller: null }

export const actions = {
  async fetchGroupByData(
    { commit, getters, rootGetters, state },
    {
      gridId,
      view,
      fields,
      adhocFiltering,
      parentPath = {},
      parentRequests = null,
      depth = null,
      offset = 0,
      limit = null,
      includeDescendants = false,
      descendantLimit = null,
      signal = null,
    }
  ) {
    const { $client, $config, $registry } = this
    const groupByGeneration = state.groupBy.generation || 0
    const groupByFields = getGroupByFieldsFromActiveGroupBys(
      getters.getActiveGroupBys,
      fields
    )
    const requestLimit = limit ?? getters.getBufferRequestSize
    const parents = parentRequests?.map((parentRequest) => {
      const mappedParent = {
        parent: parentRequest.parentPath ?? parentRequest.parent ?? {},
        offset: parentRequest.offset ?? 0,
        limit: parentRequest.limit ?? requestLimit,
      }
      const parentRowOffset =
        parentRequest.parentRowOffset ?? parentRequest.parent_row_offset
      if (parentRowOffset !== undefined && parentRowOffset !== null) {
        mappedParent.parent_row_offset = parentRowOffset
      }
      return mappedParent
    })
    const { data } = await GridService($client).fetchGroupByData({
      gridId,
      search: getters.getServerSearchTerm,
      searchMode: getDefaultSearchModeFromEnv($config),
      publicUrl: rootGetters['page/view/public/getIsPublic'],
      publicAuthToken: rootGetters['page/view/public/getAuthToken'],
      filters: getFilters(view, adhocFiltering),
      parent:
        parents === undefined && Object.keys(parentPath || {}).length > 0
          ? parentPath
          : null,
      parents,
      depth,
      offset,
      limit: requestLimit,
      includeDescendants,
      descendantLimit,
      signal,
    })
    if (isGroupByRequestStale(getters, state, groupByGeneration, signal)) {
      return data
    }
    for (const page of data.pages || []) {
      commit('SET_GROUP_BY_DATA_PAGE', {
        data: page,
        parentPath: page.parent || {},
        fields: groupByFields,
      })
    }
    placeLoadedGroupByRowsInViewport({
      commit,
      getters,
      state,
      registry: $registry,
      fields,
    })
    return data
  },
  async fetchGroupByRowsForSections(
    { commit, getters, rootGetters, state },
    {
      gridId,
      view,
      fields,
      sections,
      layout,
      includeFieldOptions = false,
      signal = null,
    }
  ) {
    const { $client, $config, $registry } = this
    const groupByGeneration = state.groupBy.generation || 0
    const groupByFields = getGroupByFieldsFromActiveGroupBys(
      getters.getActiveGroupBys,
      fields
    )
    if (sections.length === 0) {
      return { results: [], count: getters.getCount }
    }

    const startOffset = Math.min(
      ...sections.map(
        (section) => section.absoluteRowOffset + section.startPosition
      )
    )
    const endOffset = Math.max(
      ...sections.map(
        (section) => section.absoluteRowOffset + section.endPosition
      )
    )
    const bufferRequestSize = getters.getBufferRequestSize
    const requestOffset = Math.max(
      Math.floor((startOffset - bufferRequestSize) / bufferRequestSize) *
        bufferRequestSize,
      0
    )
    const countLimit = getters.getCount > 0 ? getters.getCount : endOffset
    const requestEndOffset = Math.min(
      Math.ceil((endOffset + bufferRequestSize) / bufferRequestSize) *
        bufferRequestSize,
      countLimit
    )
    const limit = requestEndOffset - requestOffset
    if (limit <= 0) {
      return { results: [], count: getters.getCount }
    }

    const search = getters.getServerSearchTerm
    const searchMode = getDefaultSearchModeFromEnv($config)
    const publicUrl = rootGetters['page/view/public/getIsPublic']
    const publicAuthToken = rootGetters['page/view/public/getAuthToken']
    const groupBy = getGroupBy(rootGetters, gridId)
    const orderBy = getOrderBy(view, getters.getAdhocSorting)
    const filters = getFilters(view, getters.getAdhocFiltering)
    const requestParams = {
      gridId,
      offset: requestOffset,
      limit,
      includeFieldOptions,
      search,
      searchMode,
      publicUrl,
      publicAuthToken,
      groupBy,
      orderBy,
      filters,
    }
    const requestKey = getGroupByRowsRequestKey(requestParams)
    const fetchRows = () =>
      GridService($client).fetchRows({
        ...requestParams,
        signal,
      })

    let rowRequest = activeGroupByRowsRequests.get(requestKey)
    if (!rowRequest) {
      rowRequest = fetchRows().finally(() => {
        if (activeGroupByRowsRequests.get(requestKey) === rowRequest) {
          activeGroupByRowsRequests.delete(requestKey)
        }
      })
      activeGroupByRowsRequests.set(requestKey, rowRequest)
    }

    const groupByRevision = state.groupBy.revision || 0
    let response
    try {
      response = await rowRequest
    } catch (error) {
      const currentRequestWasCancelled = axios.isCancel(error)
      if (currentRequestWasCancelled && !signal?.aborted) {
        response = await fetchRows()
      } else {
        throw error
      }
    }
    const { data } = response
    if (isGroupByRequestStale(getters, state, groupByGeneration, signal)) {
      return data
    }

    data.results.forEach((row) => {
      const metadata = extractRowMetadata(data, row.id)
      populateRow(row, metadata, false)
    })

    // An optimistic row mutation that landed while this fetch was in flight bumps the
    // revision. Bail before committing the server's now-stale count and field options so
    // they don't clobber the optimistic state. (`generation` guards collapse/group-by
    // changes above; `revision` guards optimistic count drift here.)
    if ((state.groupBy.revision || 0) !== groupByRevision) {
      return data
    }

    if (includeFieldOptions) {
      if (rootGetters['page/view/public/getIsPublic']) {
        commit('REPLACE_PUBLIC_FIELD_OPTIONS', data.field_options || {})
      } else {
        commit('REPLACE_ALL_FIELD_OPTIONS', data.field_options || {})
      }
    }
    if (typeof data.count === 'number') {
      commit('SET_COUNT', data.count)
    }

    const rowsByOffset = {}
    data.results.forEach((row, index) => {
      rowsByOffset[requestOffset + index] = row
    })
    commit('SET_GROUP_BY_ABSOLUTE_ROWS', rowsByOffset)

    const placements = buildGroupBySectionPlacements({
      layout,
      rowsByOffset,
      requestOffset,
      fetchedRowCount: data.results.length,
      groupByFields,
      registry: $registry,
    })
    placements.forEach((placement) => {
      commit('SET_GROUP_BY_SECTION_ROWS', placement)
    })

    return data
  },
  async fetchGroupByCount(
    { commit, getters, rootGetters, state },
    { gridId, view, includeFieldOptions = false }
  ) {
    const { $client, $config } = this
    const groupByGeneration = state.groupBy.generation || 0
    const { data } = await GridService($client).fetchRows({
      gridId,
      offset: 0,
      limit: 0,
      includeFieldOptions,
      includeRowMetadata: false,
      search: getters.getServerSearchTerm,
      searchMode: getDefaultSearchModeFromEnv($config),
      publicUrl: rootGetters['page/view/public/getIsPublic'],
      publicAuthToken: rootGetters['page/view/public/getAuthToken'],
      groupBy: getGroupBy(rootGetters, gridId),
      orderBy: getOrderBy(view, getters.getAdhocSorting),
      filters: getFilters(view, getters.getAdhocFiltering),
    })

    if (isGroupByRequestStale(getters, state, groupByGeneration)) {
      return data
    }

    commit('SET_COUNT', data.count || 0)

    if (includeFieldOptions) {
      if (rootGetters['page/view/public/getIsPublic']) {
        commit('REPLACE_PUBLIC_FIELD_OPTIONS', data.field_options || {})
      } else {
        commit('REPLACE_ALL_FIELD_OPTIONS', data.field_options || {})
      }
    }

    return data
  },
  async fetchGroupByFieldOptions({ dispatch }, { gridId, view }) {
    return await dispatch('fetchGroupByCount', {
      gridId,
      view,
      includeFieldOptions: true,
    })
  },
  async fetchGroupByRowsByScrollTop(
    { dispatch, commit, getters, state },
    {
      gridId,
      view,
      fields,
      scrollTop,
      includeFieldOptions = false,
      signal = null,
    }
  ) {
    const { $registry } = this
    const groupByGeneration = state.groupBy.generation || 0
    const groupByFields = getGroupByFieldsFromActiveGroupBys(
      getters.getActiveGroupBys,
      fields
    )
    const viewport = getGroupByViewport(getters, scrollTop)
    const useDepthPages = shouldUseGroupByDepthPages(state.groupBy)

    let layout = getters.getGroupByLayout
    if (
      Object.keys(state.groupBy.pages || {}).length === 0 &&
      (state.groupBy.treeNodes || []).length === 0
    ) {
      await dispatch('fetchGroupByData', {
        gridId,
        view,
        fields,
        adhocFiltering: getters.getAdhocFiltering,
        includeDescendants: state.groupBy.collapse?.mode === 'expand',
        descendantLimit: getters.getBufferRequestSize,
        signal,
      })
      if (isGroupByRequestStale(getters, state, groupByGeneration, signal)) {
        return []
      }
      layout = getters.getGroupByLayout
    }

    const seenPageRequests = new Set()
    const seenDepthRequests = new Set()
    for (let depth = 0; depth < groupByFields.length; depth += 1) {
      if (useDepthPages) {
        const pageToFetch = getVisibleGroupDepthPageToFetch({
          layout,
          viewport,
          pageSize: getters.getBufferRequestSize,
          seenRequests: seenDepthRequests,
        })
        if (pageToFetch === null) {
          break
        }

        await dispatch('fetchGroupByData', {
          gridId,
          view,
          fields,
          depth: pageToFetch.depth,
          offset: pageToFetch.offset,
          limit: pageToFetch.limit,
          adhocFiltering: getters.getAdhocFiltering,
          signal,
        })
        layout = getters.getGroupByLayout
        continue
      }

      const pagesToFetch = getVisibleGroupPagesToFetch({
        state,
        getters,
        layout,
        groupByFields,
        viewport,
        seenRequests: seenPageRequests,
        maxGroups: getters.getBufferRequestSize,
      })
      if (pagesToFetch.length === 0) {
        break
      }

      const rowPrefetchSections = getGroupByRowPrefetchSections({
        state,
        pageRequests: pagesToFetch,
        groupByFields,
        maxRows: getters.getBufferRequestSize * 3,
      })
      const rowPrefetch =
        rowPrefetchSections.length > 0
          ? dispatch('fetchGroupByRowsForSections', {
              gridId,
              view,
              fields,
              sections: rowPrefetchSections,
              layout,
              includeFieldOptions: false,
              signal,
            })
          : Promise.resolve()

      await Promise.all([
        rowPrefetch,
        dispatch('fetchGroupByData', {
          gridId,
          view,
          fields,
          parentRequests: pagesToFetch.map((page) => ({
            parentPath: page.parentPath,
            offset: page.offset,
            limit: page.limit,
            parentRowOffset: page.parentRowOffset,
          })),
          adhocFiltering: getters.getAdhocFiltering,
          signal,
        }),
      ])
      if (isGroupByRequestStale(getters, state, groupByGeneration, signal)) {
        return []
      }
      layout = getters.getGroupByLayout
    }

    if (isGroupByRequestStale(getters, state, groupByGeneration, signal)) {
      return []
    }

    const sections = visibleSectionsInViewport(
      layout,
      viewport,
      groupByFields,
      getters.getRowHeight
    )

    placeLoadedGroupByRowsInViewport({
      commit,
      getters,
      state,
      registry: $registry,
      fields,
      layout,
      scrollTop,
    })

    // Protect the currently-visible sections, then evict the least-recently-used
    // sections beyond the cap so memory stays bounded over a long scroll session.
    commit('TOUCH_GROUP_BY_SECTIONS', {
      sectionKeys: sections.map((section) => section.sectionKey),
    })
    commit('EVICT_LRU_GROUP_BY_SECTIONS', {
      cap: GROUP_BY_MAX_RETAINED_SECTIONS,
    })

    if (includeFieldOptions && sections.length === 0) {
      await dispatch('fetchGroupByFieldOptions', { gridId, view })
      return []
    }

    const sectionsToFetch = getMissingGroupBySectionRanges(
      state.groupBy.sectionRows,
      sections,
      state.groupBy.absoluteRows,
      groupByFields,
      $registry
    )

    if (sectionsToFetch.length === 0) {
      if (includeFieldOptions) {
        await dispatch('fetchGroupByFieldOptions', { gridId, view })
      }
      return []
    }

    return [
      await dispatch('fetchGroupByRowsForSections', {
        gridId,
        view,
        fields,
        sections: sectionsToFetch,
        layout,
        includeFieldOptions,
        signal,
      }),
    ]
  },
  async toggleGroupCollapse(
    { commit, dispatch, getters },
    { path, view, fields }
  ) {
    const groupByFields = getGroupByFieldsFromActiveGroupBys(
      getters.getActiveGroupBys,
      fields
    )
    commit('TOGGLE_GROUP_BY_COLLAPSE_PATH', { path, fields: groupByFields })
    commit('CLEAR_AREA_SELECTION')
    const scrollTop = getClampedGroupByScrollTop(getters)
    commit('SET_SCROLL_TOP', scrollTop)

    await dispatch('fetchGroupByRowsByScrollTop', {
      gridId: getters.getLastGridId,
      view,
      fields,
      scrollTop,
      includeFieldOptions: false,
    })
  },
  async setGroupByCollapseAll(
    { commit, dispatch, getters },
    { view, fields, collapse }
  ) {
    commit('SET_GROUP_BY_COLLAPSE', getGroupByCollapseAllState(collapse))
    commit('CLEAR_AREA_SELECTION')
    const scrollTop = getClampedGroupByScrollTop(getters)
    commit('SET_SCROLL_TOP', scrollTop)

    await dispatch('fetchGroupByRowsByScrollTop', {
      gridId: getters.getLastGridId,
      view,
      fields,
      scrollTop,
      includeFieldOptions: false,
    })
  },
  /**
   * This action calculates which rows we would like to have in the buffer based on
   * the scroll top offset and the window height. Based on that is calculates which
   * rows we need to fetch compared to what we already have. If we need to fetch
   * anything other then we already have or waiting for a new request will be made.
   */
  fetchByScrollTop(
    { commit, getters, rootGetters, dispatch, state },
    { scrollTop, fields }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const windowHeight = getters.getWindowHeight
    const gridId = getters.getLastGridId
    const view = getViewOrFlatDefault(rootGetters, getters.getLastGridId)

    if (getters.isGroupByMode) {
      const requestKey = JSON.stringify({
        gridId,
        scrollTop,
        generation: state.groupBy.generation || 0,
      })
      if (
        lastGroupByScrollRequest !== null &&
        lastGroupByScrollRequestKey === requestKey
      ) {
        return lastGroupByScrollRequest
      }

      if (lastGroupByScrollRequest !== null) {
        lastGroupByScrollQueryController.abort()
      }

      const controller = new AbortController()
      lastGroupByScrollQueryController = controller
      lastGroupByScrollRequestKey = requestKey
      fireScrollTop.processing = true

      lastGroupByScrollRequest = dispatch('fetchGroupByRowsByScrollTop', {
        gridId,
        view,
        fields,
        scrollTop,
        signal: controller.signal,
      })
        .catch((error) => {
          if (!axios.isCancel(error)) {
            throw error
          }
        })
        .finally(() => {
          if (lastGroupByScrollQueryController !== controller) {
            return
          }
          lastGroupByScrollRequest = null
          lastGroupByScrollRequestKey = null
          lastGroupByScrollQueryController = null
          fireScrollTop.processing = false
        })

      return lastGroupByScrollRequest
    }

    // Calculate what the middle row index of the visible window based on the scroll
    // top.
    const middle = scrollTop + windowHeight / 2
    const countIndex = getters.getCount - 1
    const middleRowIndex = Math.min(
      Math.max(Math.ceil(middle / getters.getRowHeight) - 1, 0),
      countIndex
    )

    // Calculate the start and end index of the rows that are visible to the user in
    // the whole database.
    const visibleStartIndex = Math.max(
      middleRowIndex - getters.getRowPadding,
      0
    )
    const visibleEndIndex = Math.min(
      middleRowIndex + getters.getRowPadding,
      countIndex
    )

    // Calculate the start and end index of the buffer, which are the rows that we
    // load in the memory of the browser, based on all the rows in the database.
    const bufferRequestSize = getters.getBufferRequestSize
    const bufferStartIndex = Math.max(
      Math.ceil((visibleStartIndex - bufferRequestSize) / bufferRequestSize) *
        bufferRequestSize,
      0
    )
    const bufferEndIndex = Math.min(
      Math.ceil((visibleEndIndex + bufferRequestSize) / bufferRequestSize) *
        bufferRequestSize,
      getters.getCount
    )
    const bufferLimit = bufferEndIndex - bufferStartIndex

    // Determine if the user is scrolling up or down.
    const down =
      bufferStartIndex > getters.getBufferStartIndex ||
      bufferEndIndex > getters.getBufferEndIndex
    const up =
      bufferStartIndex < getters.getBufferStartIndex ||
      bufferEndIndex < getters.getBufferEndIndex

    let prependToBuffer = 0
    let appendToBuffer = 0
    let requestOffset = null
    let requestLimit = null

    // Calculate how many rows we want to add and remove from the current rows buffer in
    // the store if the buffer would transition to the desired state. Also the
    // request offset and limit are calculated for the next request based on what we
    // currently have in the buffer.
    if (down) {
      prependToBuffer = Math.max(
        -getters.getBufferLimit,
        getters.getBufferStartIndex - bufferStartIndex
      )
      appendToBuffer = Math.min(
        bufferLimit,
        bufferEndIndex - getters.getBufferEndIndex
      )
      requestOffset = Math.max(getters.getBufferEndIndex, bufferStartIndex)
      requestLimit = appendToBuffer
    } else if (up) {
      prependToBuffer = Math.min(
        bufferLimit,
        getters.getBufferStartIndex - bufferStartIndex
      )
      appendToBuffer = Math.max(
        -getters.getBufferLimit,
        bufferEndIndex - getters.getBufferEndIndex
      )
      requestOffset = Math.max(bufferStartIndex, 0)
      requestLimit = prependToBuffer
    }

    // Checks if we need to request anything and if there are any changes since the
    // last request we made. If so we need to initialize a new request.
    if (
      requestLimit > 0 &&
      (lastRequestOffset !== requestOffset || lastRequestLimit !== requestLimit)
    ) {
      fireScrollTop.processing = true
      // If another request is running we need to cancel that one because it won't
      // what we need at the moment.
      if (lastRequest !== null) {
        lastQueryController.abort()
      }

      // Doing the actual request and remember what we are requesting so we can compare
      // it when making a new request.
      lastRequestOffset = requestOffset
      lastRequestLimit = requestLimit
      lastQueryController = new AbortController()
      lastRequest = GridService($client)
        .fetchRows({
          gridId,
          offset: requestOffset,
          limit: requestLimit,
          signal: lastQueryController.signal,
          search: getters.getServerSearchTerm,
          searchMode: getDefaultSearchModeFromEnv($config),
          publicUrl: rootGetters['page/view/public/getIsPublic'],
          publicAuthToken: rootGetters['page/view/public/getAuthToken'],
          groupBy: getGroupBy(rootGetters, getters.getLastGridId),
          orderBy: getOrderBy(view, getters.getAdhocSorting),
          filters: getFilters(view, getters.getAdhocFiltering),
          excludeCount: getters.canExcludeCount,
        })
        .then(({ data }) => {
          // Don't do anything if the gridId does not match the current view gridId
          // because that probably means the user switched to another view or table, and
          // the data that is returned here shouldn't do anything.
          if (gridId !== getters.getLastGridId) {
            return
          }

          data.results.forEach((row) => {
            const metadata = extractRowMetadata(data, row.id)
            populateRow(row, metadata, false)
          })
          commit('ADD_ROWS', {
            rows: data.results,
            prependToRows: prependToBuffer,
            appendToRows: appendToBuffer,
            count: data.count,
            bufferStartIndex,
            bufferLimit,
          })
          dispatch('visibleByScrollTop')
          dispatch('updateSearch', { fields })
          lastRequest = null
          fireScrollTop.processing = false
        })
        .catch((error) => {
          if (!axios.isCancel(error)) {
            lastRequest = null
            throw error
          }
          fireScrollTop.processing = false
        })
    }
  },
  /**
   * Calculates which rows should be visible for the user based on the provided
   * scroll top and window height. Because we know what the padding above and below
   * the middle row should be and which rows we have in the buffer we can calculate
   * what the start and end index for the visible rows in the buffer should be.
   */
  visibleByScrollTop({ getters, commit }, scrollTop = null) {
    const { $registry, $client, $i18n, $config } = this
    if (scrollTop !== null) {
      commit('SET_SCROLL_TOP', scrollTop)
    } else {
      scrollTop = getters.getScrollTop
    }

    if (getters.isGroupByMode) {
      return
    }

    const windowHeight = getters.getWindowHeight
    const middle = scrollTop + windowHeight / 2
    const countIndex = getters.getCount - 1

    const middleRowIndex = Math.min(
      Math.max(Math.ceil(middle / getters.getRowHeight) - 1, 0),
      countIndex
    )

    // Calculate the start and end index of the rows that are visible to the user in
    // the whole table.
    const visibleStartIndex = Math.max(
      middleRowIndex - getters.getRowPadding,
      0
    )
    const visibleEndIndex = Math.min(
      middleRowIndex + getters.getRowPadding + 1,
      getters.getCount
    )

    // Calculate the start and end index of the buffered rows that are visible for
    // the user.
    const visibleRowStartIndex =
      Math.min(
        Math.max(visibleStartIndex, getters.getBufferStartIndex),
        getters.getBufferEndIndex
      ) - getters.getBufferStartIndex
    const visibleRowEndIndex =
      Math.max(
        Math.min(visibleEndIndex, getters.getBufferEndIndex),
        getters.getBufferStartIndex
      ) - getters.getBufferStartIndex

    // Calculate the top position of the html element that contains all the rows.
    // This element will be placed over the placeholder the correct position of
    // those rows.
    const top =
      Math.min(visibleStartIndex, getters.getBufferEndIndex) *
      getters.getRowHeight

    // If the index changes from what we already have we can commit the new indexes
    // to the state.
    if (
      visibleRowStartIndex !== getters.getRowsStartIndex ||
      visibleRowEndIndex !== getters.getRowsEndIndex ||
      top !== getters.getRowsTop
    ) {
      commit('SET_ROWS_INDEX', {
        startIndex: visibleRowStartIndex,
        endIndex: visibleRowEndIndex,
        top,
      })
    }
  },
  /**
   * This action is called every time the users scrolls which might result in a lot
   * of calls. Therefore it will dispatch the related actions, but only every 100
   * milliseconds to prevent calling the actions who do a lot of calculating a lot.
   */
  fetchByScrollTopDelayed({ dispatch }, { scrollTop, fields }) {
    const { $registry, $client, $i18n, $config } = this
    const now = Date.now()

    const fire = (scrollTop) => {
      fireScrollTop.distance = scrollTop
      fireScrollTop.last = now
      dispatch('fetchByScrollTop', {
        scrollTop,
        fields,
      })
      dispatch('visibleByScrollTop', scrollTop)
    }

    const distance = Math.abs(scrollTop - fireScrollTop.distance)
    const timeDelta = now - fireScrollTop.last
    const velocity = distance / timeDelta

    if (!fireScrollTop.processing && timeDelta > 100 && velocity < 2.5) {
      clearTimeout(fireScrollTop.timeout)
      fire(scrollTop)
    } else {
      // Allow velocity calculation on last ~100 ms
      if (timeDelta > 100) {
        fireScrollTop.distance = scrollTop
        fireScrollTop.last = now
      }
      clearTimeout(fireScrollTop.timeout)
      fireScrollTop.timeout = setTimeout(() => {
        fire(scrollTop)
      }, 100)
    }
  },
  /**
   * Fetches an initial set of rows and adds that data to the store.
   */
  async fetchInitial(
    { dispatch, commit, getters, rootGetters },
    { gridId, fields, adhocFiltering, adhocSorting }
  ) {
    const { $registry, $client, $i18n, $config } = this
    // Reset scrollTop when switching table
    fireScrollTop.distance = 0
    fireScrollTop.last = Date.now()
    fireScrollTop.processing = false

    commit('SET_SEARCH', {
      activeSearchTerm: '',
      hideRowsNotMatchingSearch: true,
    })
    commit('SET_LAST_GRID_ID', gridId)
    commit('SET_ADHOC_FILTERING', adhocFiltering)
    commit('SET_ADHOC_SORTING', adhocSorting)

    const view = getViewOrFlatDefault(rootGetters, getters.getLastGridId)
    commit('SET_ACTIVE_GROUP_BYS', clone(view.group_bys || []))
    const limit = getters.getBufferRequestSize * 2

    if (getters.isGroupByMode) {
      commit('CLEAR_ROWS')
      commit('SET_LAST_GRID_ID', gridId)
      commit('SET_ADHOC_FILTERING', adhocFiltering)
      commit('SET_ADHOC_SORTING', adhocSorting)
      commit('SET_GROUP_BY_COLLAPSE', getGroupByCollapseAllState(false))
      await dispatch('fetchGroupByData', {
        gridId,
        view,
        fields,
        adhocFiltering,
        includeDescendants: true,
        descendantLimit: getters.getBufferRequestSize,
      })
      await dispatch('fetchGroupByRowsByScrollTop', {
        gridId,
        view,
        fields,
        scrollTop: 0,
        includeFieldOptions: true,
      })
      dispatch('updateSearch', { fields })
      return
    }

    const { data } = await GridService($client).fetchRows({
      gridId,
      offset: 0,
      limit,
      includeFieldOptions: true,
      search: getters.getServerSearchTerm,
      searchMode: getDefaultSearchModeFromEnv($config),
      publicUrl: rootGetters['page/view/public/getIsPublic'],
      publicAuthToken: rootGetters['page/view/public/getAuthToken'],
      groupBy: getGroupBy(rootGetters, getters.getLastGridId),
      orderBy: getOrderBy(view, adhocSorting),
      filters: getFilters(view, adhocFiltering),
    })
    // Don't do anything if the gridId does not match the current view gridId
    // because that probably means the user switched to another view or table, and
    // the data that is returned here shouldn't do anything.
    if (gridId !== getters.getLastGridId) {
      return
    }
    data.results.forEach((row) => {
      const metadata = extractRowMetadata(data, row.id)
      populateRow(row, metadata, false)
    })
    commit('CLEAR_ROWS')
    commit('ADD_ROWS', {
      rows: data.results,
      prependToRows: 0,
      appendToRows: data.results.length,
      count: data.count,
      bufferStartIndex: 0,
      bufferLimit: data.count > limit ? limit : data.count,
    })
    commit('SET_ROWS_INDEX', {
      startIndex: 0,
      // Initial row-index window sized to roughly one screen of rows; the scroll
      // handler widens it once the real viewport height is known.
      endIndex: data.count > 31 ? 31 : data.count,
      top: 0,
    })
    commit('REPLACE_ALL_FIELD_OPTIONS', data.field_options)

    dispatch('updateSearch', { fields })
  },
  /**
   * Refreshes the current state with fresh data. It keeps the scroll offset the same
   * if possible. This can be used when a new filter or sort is created. Will also
   * update search highlighting if a new activeSearchTerm and hideRowsNotMatchingSearch
   * are provided in the refreshEvent.
   */
  refresh(
    { dispatch, commit, getters, rootGetters, state },
    {
      view,
      fields,
      adhocFiltering,
      adhocSorting,
      includeFieldOptions = false,
      sourceEvent = null,
    }
  ) {
    const { $client, $config } = this
    const previousGroupByMode = getters.isGroupByMode
    const previousGroupByCollapse = clone(getters.getGroupByCollapse)
    const previousGroupByCollapseInitialized =
      state.groupBy.collapseInitialized === true
    const previousGroupByFields = getGroupByFieldsFromActiveGroupBys(
      state.activeGroupBys,
      fields
    )
    const nextGroupBys = clone(view.group_bys || [])
    const groupBysChanged = !_.isEqual(state.activeGroupBys || [], nextGroupBys)
    commit('SET_ADHOC_FILTERING', adhocFiltering)
    commit('SET_ADHOC_SORTING', adhocSorting)
    const nextGroupByFields = getGroupByFieldsFromActiveGroupBys(
      nextGroupBys,
      fields
    )
    const gridId = getters.getLastGridId

    if (groupBysChanged && nextGroupByFields.length > 0) {
      return Promise.resolve()
        .then(async () => {
          const handled = await dispatch('refreshActiveGroupBys', {
            view,
            fields,
            scrollTop: getters.getScrollTop,
            includeFieldOptions,
          })
          if (!handled) {
            return
          }
          dispatch('correctMultiSelect')
          dispatch('fetchAllFieldAggregationData', { view })
        })
        .catch((error) => {
          if (axios.isCancel(error)) {
            throw new RefreshCancelledError()
          }
          throw error
        })
    }

    commit('SET_ACTIVE_GROUP_BYS', nextGroupBys)

    if (getters.isGroupByMode && sourceEvent === 'sort') {
      const refresh = Promise.resolve()
        .then(async () => {
          commit('CLEAR_GROUP_BY_SECTION_ROWS')
          await dispatch('fetchGroupByRowsByScrollTop', {
            gridId,
            view,
            fields,
            scrollTop: getters.getScrollTop,
            includeFieldOptions,
          })
          dispatch('correctMultiSelect')
        })
        .catch((error) => {
          if (axios.isCancel(error)) {
            throw new RefreshCancelledError()
          }
          throw error
        })
      return refresh
    }

    if (getters.isGroupByMode) {
      const groupByFields = getGroupByFieldsFromActiveGroupBys(
        nextGroupBys,
        fields
      )
      const groupByCollapse =
        previousGroupByMode || previousGroupByCollapseInitialized
          ? projectGroupByCollapseState(
              previousGroupByCollapse,
              previousGroupByFields,
              groupByFields
            )
          : getGroupByCollapseAllState(false)
      const refresh = Promise.resolve()
        .then(async () => {
          commit('SET_GROUP_BY_COLLAPSE', groupByCollapse)
          commit('RESET_GROUP_BY_DATA')
          await dispatch('fetchGroupByData', {
            gridId,
            view,
            fields,
            adhocFiltering,
            includeDescendants: groupByCollapse.mode === 'expand',
            descendantLimit: getters.getBufferRequestSize,
          })
          await dispatch('fetchGroupByRowsByScrollTop', {
            gridId,
            view,
            fields,
            scrollTop: getters.getScrollTop,
            includeFieldOptions,
          })
          dispatch('correctMultiSelect')
          dispatch('fetchAllFieldAggregationData', { view })
        })
        .catch((error) => {
          if (axios.isCancel(error)) {
            throw new RefreshCancelledError()
          }
          throw error
        })
      return refresh
    }

    if (lastRefreshRequest !== null) {
      lastRefreshRequestController.abort()
    }
    lastRefreshRequestController = new AbortController()
    lastRefreshRequest = GridService($client)
      .fetchCount({
        gridId,
        search: getters.getServerSearchTerm,
        searchMode: getDefaultSearchModeFromEnv($config),
        signal: lastRefreshRequestController.signal,
        publicUrl: rootGetters['page/view/public/getIsPublic'],
        publicAuthToken: rootGetters['page/view/public/getAuthToken'],
        filters: getFilters(view, adhocFiltering),
      })
      .then((response) => {
        const count = response.data.count

        const limit = getters.getBufferRequestSize * 3
        const bufferEndIndex = getters.getBufferEndIndex
        const offset =
          count >= bufferEndIndex
            ? getters.getBufferStartIndex
            : Math.max(0, count - limit)
        return { limit, offset, count }
      })
      .then(({ limit, offset, count }) =>
        GridService($client)
          .fetchRows({
            gridId,
            offset,
            limit,
            includeFieldOptions,
            signal: lastRefreshRequestController.signal,
            search: getters.getServerSearchTerm,
            searchMode: getDefaultSearchModeFromEnv($config),
            publicUrl: rootGetters['page/view/public/getIsPublic'],
            publicAuthToken: rootGetters['page/view/public/getAuthToken'],
            groupBy: getGroupBy(rootGetters, getters.getLastGridId),
            orderBy: getOrderBy(view, adhocSorting),
            filters: getFilters(view, adhocFiltering),
            excludeCount: true, // We already have it from the previous request.
          })
          .then(({ data }) => ({
            data: { ...data, count },
            offset,
          }))
      )
      .then(({ data, offset }) => {
        // Don't do anything if the gridId does not match the current view gridId
        // because that probably means the user switched to another view or table, and
        // the data that is returned here shouldn't do anything.
        if (gridId !== getters.getLastGridId) {
          return
        }
        // If there are results we can replace the existing rows so that the user stays
        // at the same scroll offset.
        data.results.forEach((row) => {
          const metadata = extractRowMetadata(data, row.id)
          populateRow(row, metadata, false)
        })
        commit('ADD_ROWS', {
          rows: data.results,
          prependToRows: -getters.getBufferLimit,
          appendToRows: data.results.length,
          count: data.count,
          bufferStartIndex: offset,
          bufferLimit: data.results.length,
        })

        dispatch('updateSearch', { fields })
        if (includeFieldOptions) {
          if (rootGetters['page/view/public/getIsPublic']) {
            commit('REPLACE_PUBLIC_FIELD_OPTIONS', data.field_options)
          } else {
            commit('REPLACE_ALL_FIELD_OPTIONS', data.field_options)
          }
        }
        dispatch('correctMultiSelect')
        dispatch('fetchAllFieldAggregationData', {
          view,
        })
        lastRefreshRequest = null
      })
      .catch((error) => {
        if (axios.isCancel(error)) {
          throw new RefreshCancelledError()
        } else {
          lastRefreshRequest = null
          throw error
        }
      })
    return lastRefreshRequest
  },
  async refreshActiveGroupBys(
    { commit, getters, rootGetters, state },
    { view, fields, scrollTop, includeFieldOptions = false }
  ) {
    const { $client, $config, $registry } = this
    const nextGroupBys = clone(view.group_bys || [])
    const previousGroupBys = state.activeGroupBys || []
    if (_.isEqual(previousGroupBys, nextGroupBys)) {
      return false
    }
    if (nextGroupBys.length === 0) {
      return false
    }

    const gridId = getters.getLastGridId
    const groupByFields = getGroupByFieldsFromActiveGroupBys(
      nextGroupBys,
      fields
    )
    if (groupByFields.length === 0) {
      return false
    }

    // Changing the group-by fields rebuilds the whole layout, so the previous scroll
    // offset points at an unloaded region of the new tree and would leave the viewport
    // blank. Restart at the top, where this refresh fetches the first page.
    scrollTop = 0
    commit('SET_SCROLL_TOP', 0)
    fireScrollTop.distance = 0
    fireScrollTop.last = Date.now()
    fireScrollTop.processing = false

    const previousGroupByFields = getGroupByFieldsFromActiveGroupBys(
      previousGroupBys,
      fields
    )
    const previousGroupByMode = previousGroupBys.length > 0
    const previousGroupByCollapse = clone(getters.getGroupByCollapse)
    const previousGroupByCollapseInitialized =
      state.groupBy.collapseInitialized === true
    let groupByCollapse =
      previousGroupByMode || previousGroupByCollapseInitialized
        ? projectGroupByCollapseState(
            previousGroupByCollapse,
            previousGroupByFields,
            groupByFields
          )
        : getGroupByCollapseAllState(false)

    // A per-group (mixed) collapse can't be expressed by the single `includeDescendants`
    // flag of the fresh multi-level fetch below: the deeper group nodes of an expanded
    // branch never get fetched, so the branch renders empty. Fall back to expand-all,
    // which fetches the whole visible tree. Single-level views are unaffected because
    // their rows are fetched separately regardless of the flag.
    if (groupByFields.length > 1 && groupByCollapse.paths.length > 0) {
      groupByCollapse = getGroupByCollapseAllState(false)
    }

    commit('INVALIDATE_GROUP_BY_REQUESTS')
    const groupByGeneration = state.groupBy.generation || 0
    const snapshot = {
      ...getEmptyGroupByState(),
      generation: groupByGeneration,
      collapse: groupByCollapse,
      collapseInitialized: true,
    }

    const { data: groupByData } = await GridService($client).fetchGroupByData({
      gridId,
      search: getters.getServerSearchTerm,
      searchMode: getDefaultSearchModeFromEnv($config),
      publicUrl: rootGetters['page/view/public/getIsPublic'],
      publicAuthToken: rootGetters['page/view/public/getAuthToken'],
      filters: getFilters(view, getters.getAdhocFiltering),
      offset: 0,
      limit: getters.getBufferRequestSize,
      includeDescendants: groupByCollapse.mode === 'expand',
      descendantLimit: getters.getBufferRequestSize,
    })
    if ((state.groupBy.generation || 0) !== groupByGeneration) {
      return true
    }

    for (const page of groupByData.pages || []) {
      mergeGroupByDataPageInto(snapshot, {
        data: page,
        parentPath: page.parent || {},
        fields: groupByFields,
      })
    }

    const viewport = getGroupByViewport(getters, scrollTop)
    const layout = getGroupBySnapshotLayout(
      snapshot,
      nextGroupBys,
      fields,
      state
    )
    const sections = visibleSectionsInViewport(
      layout,
      viewport,
      groupByFields,
      getters.getRowHeight
    )

    let rowData = null
    if (sections.length > 0) {
      const startOffset = Math.min(
        ...sections.map(
          (section) => section.absoluteRowOffset + section.startPosition
        )
      )
      const endOffset = Math.max(
        ...sections.map(
          (section) => section.absoluteRowOffset + section.endPosition
        )
      )
      const requestOffset = startOffset
      const limit = Math.max(0, endOffset - startOffset)

      if (limit > 0) {
        const { data } = await GridService($client).fetchRows({
          gridId,
          offset: requestOffset,
          limit,
          includeFieldOptions,
          search: getters.getServerSearchTerm,
          searchMode: getDefaultSearchModeFromEnv($config),
          publicUrl: rootGetters['page/view/public/getIsPublic'],
          publicAuthToken: rootGetters['page/view/public/getAuthToken'],
          groupBy: getGroupBy(rootGetters, gridId),
          orderBy: getOrderBy(view, getters.getAdhocSorting),
          filters: getFilters(view, getters.getAdhocFiltering),
          excludeCount: getters.canExcludeCount,
        })
        if ((state.groupBy.generation || 0) !== groupByGeneration) {
          return true
        }
        rowData = data
        rowData.results.forEach((row) => {
          const metadata = extractRowMetadata(rowData, row.id)
          populateRow(row, metadata, false)
        })

        const rowsByOffset = {}
        rowData.results.forEach((row, index) => {
          rowsByOffset[requestOffset + index] = row
        })
        snapshot.absoluteRows = {
          ...snapshot.absoluteRows,
          ...rowsByOffset,
        }

        const placements = buildGroupBySectionPlacements({
          layout,
          rowsByOffset,
          requestOffset,
          fetchedRowCount: rowData.results.length,
          groupByFields,
          registry: $registry,
        })
        placements.forEach((placement) => {
          setGroupBySectionRowsInto(snapshot, state, placement)
        })
      }
    }

    commit('APPLY_GROUP_BY_STATE', {
      activeGroupBys: nextGroupBys,
      groupBy: snapshot,
      count: rowData?.count,
    })
    if (includeFieldOptions && rowData?.field_options) {
      if (rootGetters['page/view/public/getIsPublic']) {
        commit('REPLACE_PUBLIC_FIELD_OPTIONS', rowData.field_options)
      } else {
        commit('REPLACE_ALL_FIELD_OPTIONS', rowData.field_options)
      }
    }
    return true
  },
  updateActiveGroupBys({ commit, state }, groupBys) {
    const nextGroupBys = groupBys || []
    const changed = !_.isEqual(state.activeGroupBys || [], nextGroupBys)
    commit('SET_ACTIVE_GROUP_BYS', nextGroupBys)
    if (changed) {
      commit('RESET_GROUP_BY_DATA')
    }
  },
  /**
   * Updates the field options of a given field and also makes an API request to the
   * backend with the changed values. If the request fails the action is reverted.
   */
  async updateFieldOptionsOfField(
    { commit, getters, dispatch, rootGetters },
    { field, values, oldValues, readOnly = false, undoRedoActionGroupId }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const previousOptions = getters.getAllFieldOptions[field.id]
    let needAggregationValueUpdate = false

    /**
     * If the aggregation raw type has changed, we delete the corresponding the
     * aggregation value from the store.
     */
    if (
      Object.prototype.hasOwnProperty.call(values, 'aggregation_raw_type') &&
      values.aggregation_raw_type !== previousOptions.aggregation_raw_type
    ) {
      needAggregationValueUpdate = true
      commit('SET_FIELD_AGGREGATION_DATA', { fieldId: field.id, value: null })
      commit('SET_FIELD_AGGREGATION_DATA_LOADING', {
        fieldId: field.id,
        value: true,
      })
    }

    commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
      fieldId: field.id,
      values,
    })

    const gridId = getters.getLastGridId
    if (!readOnly) {
      const updateValues = { field_options: {} }
      updateValues.field_options[field.id] = values

      try {
        await ViewService($client).updateFieldOptions({
          viewId: gridId,
          values: updateValues,
          undoRedoActionGroupId,
        })
      } catch (error) {
        commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
          fieldId: field.id,
          values: oldValues,
        })
        throw error
      } finally {
        if (needAggregationValueUpdate && values.aggregation_type) {
          dispatch('fetchAllFieldAggregationData', { view: { id: gridId } })
        }
      }
    }
  },
  /**
   * Updates the field options of a given field in the store. So no API request to
   * the backend is made.
   */
  setFieldOptionsOfField({ commit, getters, dispatch }, { field, values }) {
    const { $registry, $client, $i18n, $config } = this
    commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
      fieldId: field.id,
      values,
    })
    dispatch('correctMultiSelect')
  },
  /**
   * Replaces all field options with new values and also makes an API request to the
   * backend with the changed values. If the request fails the action is reverted.
   */
  async updateAllFieldOptions(
    { dispatch, getters, rootGetters },
    {
      newFieldOptions,
      oldFieldOptions,
      readOnly = false,
      undoRedoActionGroupId = null,
    }
  ) {
    const { $registry, $client, $i18n, $config } = this
    dispatch('forceUpdateAllFieldOptions', newFieldOptions)

    const gridId = getters.getLastGridId
    if (!readOnly) {
      const updateValues = { field_options: newFieldOptions }

      try {
        await ViewService($client).updateFieldOptions({
          viewId: gridId,
          values: updateValues,
          undoRedoActionGroupId,
        })
      } catch (error) {
        dispatch('forceUpdateAllFieldOptions', oldFieldOptions)
        dispatch('correctMultiSelect')
        throw error
      }
    }
  },
  /**
   * Forcefully updates all field options without making a call to the backend.
   */
  forceUpdateAllFieldOptions({ commit, dispatch }, fieldOptions) {
    commit('UPDATE_ALL_FIELD_OPTIONS', fieldOptions)
    dispatch('correctMultiSelect')
  },
  /**
   * Fetch all field aggregation data from the server for this view. Set loading state
   * to true while doing the query. Do nothing if this is a public view or if there is
   * no aggregation at all. If the query goes in error, the values are set to `null`
   * to prevent wrong information.
   * If a request is already in progress, it is aborted in favour of the new one.
   */
  async fetchAllFieldAggregationData(
    { rootGetters, getters, commit },
    { view }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const isPublic = rootGetters['page/view/public/getIsPublic']
    const search = getters.getActiveSearchTerm
    const fieldOptions = getters.getAllFieldOptions
    const gridId = getters.getLastGridId
    let atLeastOneAggregation = false

    Object.entries(fieldOptions).forEach(([fieldId, options]) => {
      if (options.aggregation_raw_type) {
        commit('SET_FIELD_AGGREGATION_DATA_LOADING', {
          fieldId,
          value: true,
        })
        atLeastOneAggregation = true
      }
    })

    if (!atLeastOneAggregation) {
      return
    }

    try {
      if (lastAggregationRequest.request !== null) {
        lastAggregationRequest.controller.abort()
      }

      lastAggregationRequest.controller = new AbortController()

      if (!isPublic) {
        lastAggregationRequest.request = GridService(
          $client
        ).fetchFieldAggregations({
          gridId: view.id,
          filters: getFilters(view, getters.getAdhocFiltering),
          search,
          searchMode: getDefaultSearchModeFromEnv($config),
          signal: lastAggregationRequest.controller.signal,
        })
      } else {
        lastAggregationRequest.request = GridService(
          $client
        ).fetchPublicFieldAggregations({
          slug: view.slug,
          publicAuthToken: rootGetters['page/view/public/getAuthToken'],
          filters: getFilters(view, getters.getAdhocFiltering),
          search,
          searchMode: getDefaultSearchModeFromEnv($config),
          signal: lastAggregationRequest.controller.signal,
        })
      }

      const { data } = await lastAggregationRequest.request
      lastAggregationRequest.request = null

      // Don't do anything if the gridId does not match the current view gridId
      // because that probably means the user switched to another view or table, and
      // the data that is returned here shouldn't do anything.
      if (gridId !== getters.getLastGridId) {
        return
      }

      Object.entries(fieldOptions).forEach(([fieldId, options]) => {
        if (options.aggregation_raw_type) {
          commit('SET_FIELD_AGGREGATION_DATA', {
            fieldId,
            value: data[`field_${fieldId}`],
          })
        }
      })

      Object.entries(fieldOptions).forEach(([fieldId, options]) => {
        if (options.aggregation_raw_type) {
          commit('SET_FIELD_AGGREGATION_DATA_LOADING', {
            fieldId,
            value: false,
          })
        }
      })
    } catch (error) {
      if (!axios.isCancel(error)) {
        lastAggregationRequest.request = null

        // Emptied the values
        Object.entries(fieldOptions).forEach(([fieldId, options]) => {
          if (options.aggregation_raw_type) {
            commit('SET_FIELD_AGGREGATION_DATA', {
              fieldId,
              value: null,
            })
          }
        })

        // Remove loading state
        Object.entries(fieldOptions).forEach(([fieldId, options]) => {
          if (options.aggregation_raw_type) {
            commit('SET_FIELD_AGGREGATION_DATA_LOADING', {
              fieldId,
              value: false,
            })
          }
        })

        throw error
      }
    }
  },
  /**
   * Updates the order of all the available field options. The provided order parameter
   * should be an array containing the field ids in the correct order.
   */
  async updateFieldOptionsOrder(
    { commit, getters, dispatch },
    { order, readOnly = false, undoRedoActionGroupId = null }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const oldFieldOptions = clone(getters.getAllFieldOptions)
    const newFieldOptions = clone(getters.getAllFieldOptions)

    // Update the order of the field options that have not been provided in the order.
    // They will get a position that places them after the provided field ids.
    let i = 0
    Object.keys(newFieldOptions).forEach((fieldId) => {
      if (!order.includes(parseInt(fieldId))) {
        newFieldOptions[fieldId].order = order.length + i
        i++
      }
    })

    // Update create the field options and set the correct order value.
    order.forEach((fieldId, index) => {
      const id = fieldId.toString()
      if (Object.prototype.hasOwnProperty.call(newFieldOptions, id)) {
        newFieldOptions[fieldId.toString()].order = index
      }
    })

    return await dispatch('updateAllFieldOptions', {
      oldFieldOptions,
      newFieldOptions,
      readOnly,
      undoRedoActionGroupId,
    })
  },
  /**
   * Move one field on the left or the right of the specified `fromField`
   * by updating all the fieldOptions orders.
   *
   * @param {object} fieldToMove The field that is going to be moved.
   * @param {string} position Set to 'left' to move the field to the left of the
   *                          fromField. The field is moved to the right otherwise.
   * @param {object} fromField We want to move the `fieldtoMove` relatively to this
   *                           field.
   *                           If `position` === 'left' the `fieldToMove` is going to be
   *                           positioned at the left of the specified `fromField`
   *                           otherwise to the right of this field.
   * @param {string} undoRedoActionGroupId An optional undo/redo group action.
   * @param {boolean} readOnly Set to true to not send the modification to the server.
   */
  async updateSingleFieldOptionOrder(
    { getters, dispatch },
    {
      fieldToMove,
      position = 'left',
      fromField,
      undoRedoActionGroupId = null,
      readOnly = false,
      visible = null,
    }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const oldFieldOptions = clone(getters.getAllFieldOptions)
    const newFieldOptions = clone(getters.getAllFieldOptions)

    // Order field options by order then by fieldId
    const orderedFieldOptions = Object.entries(newFieldOptions)
      .map(([fieldIdStr, options]) => [parseInt(fieldIdStr), options])
      .sort(([a, { order: orderA }], [b, { order: orderB }]) => {
        // First by order.
        if (orderA > orderB) {
          return 1
        } else if (orderA < orderB) {
          return -1
        }

        return a - b
      })

    let index = 0
    // Update order of all fieldOptions inserting the movedField to the right position
    orderedFieldOptions.forEach(([fieldId, options]) => {
      if (fieldId === fromField.id) {
        // Update firstField and second field order
        if (position === 'left') {
          newFieldOptions[fieldToMove.id].order = index
          newFieldOptions[fromField.id].order = index + 1
        } else {
          newFieldOptions[fromField.id].order = index
          newFieldOptions[fieldToMove.id].order = index + 1
        }
        index += 2
      } else if (fieldId !== fieldToMove.id) {
        // Update all other field order
        options.order = index
        index += 1
      } else if (visible !== null) {
        // Make the moved field visible if the `visible` parameter is not null
        newFieldOptions[fieldId].hidden = !visible
      }
    })

    return await dispatch('updateAllFieldOptions', {
      oldFieldOptions,
      newFieldOptions,
      readOnly,
      undoRedoActionGroupId,
    })
  },
  /**
   * Deletes the field options of the provided field id if they exist.
   */
  forceDeleteFieldOptions({ commit, dispatch }, fieldId) {
    commit('DELETE_FIELD_OPTIONS', fieldId)
    dispatch('correctMultiSelect')
  },
  setWindowHeight({ dispatch, commit, getters }, value) {
    commit('SET_WINDOW_HEIGHT', value)
    commit('SET_ROW_PADDING', Math.ceil(value / getters.getRowHeight / 2))
    dispatch('visibleByScrollTop')
  },
  setAddRowHover({ commit }, value) {
    commit('SET_ADD_ROW_HOVER', value)
  },
  setSelectedCell({ commit, getters }, { rowId, fieldId, fields }) {
    commit('SET_SELECTED_CELL', { rowId, fieldId })

    const rowIndex = getters.getRowIndexById(rowId)

    if (rowIndex !== -1) {
      commit('SET_MULTISELECT_START_ROW_INDEX', rowIndex)
      const visibleFieldOptions = getters.getOrderedVisibleFieldOptions(fields)
      commit(
        'SET_MULTISELECT_START_FIELD_INDEX',
        visibleFieldOptions.findIndex((f) => parseInt(f[0]) === fieldId)
      )
    }
  },
  setSelectedCellCancelledMultiSelect(
    { commit, getters, rootGetters, dispatch },
    { direction, fields }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const selectionType = getters.getSelectionType
    const rowIndex = getters.getMultiSelectStartRowIndex
    const fieldIndex = getters.getMultiSelectStartFieldIndex
    const [newRowIndex, newFieldIndex] = updatePositionFn[direction](
      rowIndex,
      fieldIndex
    )

    // In group-by mode the visible row index maps through the layout (collapsed and
    // unloaded ranges create gaps), so resolve it via getRowIdByIndex rather than
    // indexing the compacted loaded-rows buffer directly.
    const resolveRowByIndex = (visibleIndex) =>
      getters.isGroupByMode
        ? getters.getRow(getters.getRowIdByIndex(visibleIndex))
        : getters.getAllRows[visibleIndex - getters.getBufferStartIndex]
    const visibleFieldEntries = getters.getOrderedVisibleFieldOptions(fields)
    const row = resolveRowByIndex(newRowIndex)
    const field = visibleFieldEntries[newFieldIndex]

    if (row && field) {
      if (
        selectionType === GRID_VIEW_MULTI_SELECT_CHECKBOX &&
        getters.hasSelectedCell
      ) {
        dispatch('clearCheckboxSelections')
        dispatch('setSelectionType', { selectionType: null })
      }
      dispatch('setSelectedCell', {
        rowId: row.id,
        fieldId: parseInt(field[0]),
        fields,
      })
    } else {
      const oldRow = resolveRowByIndex(rowIndex)
      const oldField = visibleFieldEntries[fieldIndex]

      if (oldRow && oldField) {
        if (
          selectionType === GRID_VIEW_MULTI_SELECT_CHECKBOX &&
          getters.hasSelectedCell
        ) {
          dispatch('clearCheckboxSelections')
          dispatch('setSelectionType', { selectionType: null })
        }
        dispatch('setSelectedCell', {
          rowId: oldRow.id,
          fieldId: parseInt(oldField[0]),
          fields,
        })
      }
    }

    if (selectionType !== GRID_VIEW_MULTI_SELECT_CHECKBOX) {
      dispatch('clearAndDisableMultiSelect')
    }
  },
  setMultiSelectHolding({ commit }, value) {
    commit('SET_MULTISELECT_HOLDING', value)
  },
  setMultiSelectActive({ commit }, value) {
    commit('SET_MULTISELECT_ACTIVE', value)
  },
  clearCheckboxSelections({ commit }) {
    commit('CLEAR_CHECKBOX_SELECTION')
  },
  clearAndDisableMultiSelect({ commit, dispatch, state }) {
    commit('CLEAR_AREA_SELECTION')
    dispatch('clearCheckboxSelections', { commit, state })
    commit('SET_MULTISELECT_ACTIVE', false)
    commit('SET_SELECTION_TYPE', null)
  },
  multiSelectStart({ getters, commit, dispatch }, { rowId, fieldIndex }) {
    dispatch('setSelectionType', { selectionType: GRID_VIEW_MULTI_SELECT_AREA })

    const rowIndex = getters.getRowIndexById(rowId)
    // Update the store to show that the mouse is being held for multi-select
    commit('SET_MULTISELECT_START_ROW_INDEX', rowIndex)
    commit('SET_MULTISELECT_START_FIELD_INDEX', fieldIndex)
    commit('SET_MULTISELECT_HEAD_ROW_INDEX', rowIndex)
    commit('SET_MULTISELECT_HEAD_FIELD_INDEX', fieldIndex)
    commit('SET_MULTISELECT_TAIL_ROW_INDEX', rowIndex)
    commit('SET_MULTISELECT_TAIL_FIELD_INDEX', fieldIndex)
    commit('SET_MULTISELECT_HOLDING', true)
    // Do not enable multi-select if only a single cell is selected
    commit('SET_MULTISELECT_ACTIVE', false)
  },
  multiSelectShiftClick(
    { state, getters, commit, dispatch },
    { rowId, fieldIndex }
  ) {
    commit('SET_MULTISELECT_ACTIVE', true)
    dispatch('setSelectionType', { selectionType: GRID_VIEW_MULTI_SELECT_AREA })
    dispatch('setMultiSelectHeadOrTail', { rowId, fieldIndex })
  },
  multiSelectShiftChange({ getters, commit, dispatch }, { direction }) {
    const { $registry, $client, $i18n, $config } = this
    if (
      getters.getMultiSelectStartRowIndex === -1 ||
      getters.getMultiSelectStartFieldIndex === -1
    ) {
      return {
        position: null,
        rowIndex: -1,
        fieldIndex: -1,
      }
    }

    if (!getters.isMultiSelectActive) {
      commit('SET_MULTISELECT_ACTIVE', true)
      dispatch('setSelectionType', {
        selectionType: GRID_VIEW_MULTI_SELECT_AREA,
      })
      dispatch('updateMultipleSelectIndexes', {
        position: 'head',
        rowIndex: getters.getMultiSelectStartRowIndex,
        fieldIndex: getters.getMultiSelectStartFieldIndex,
      })
      dispatch('updateMultipleSelectIndexes', {
        position: 'tail',
        rowIndex: getters.getMultiSelectStartRowIndex,
        fieldIndex: getters.getMultiSelectStartFieldIndex,
      })
      commit('SET_SELECTED_CELL', { rowId: -1, fieldId: -1 })
    }

    const tailRowIndex = getters.getMultiSelectTailRowIndex
    const tailFieldIndex = getters.getMultiSelectTailFieldIndex
    const headRowIndex = getters.getMultiSelectHeadRowIndex
    const headFieldIndex = getters.getMultiSelectHeadFieldIndex

    const [newRowTailIndex, newFieldTailIndex] = updatePositionFn[direction](
      tailRowIndex,
      tailFieldIndex
    )
    const [newRowHeadIndex, newFieldHeadIndex] = updatePositionFn[direction](
      headRowIndex,
      headFieldIndex
    )
    let positionToMove

    if (direction === 'below') {
      if (headRowIndex === getters.getMultiSelectStartRowIndex) {
        positionToMove = 'tail'
      } else {
        positionToMove = 'head'
      }
    }

    if (direction === 'above') {
      if (tailRowIndex === getters.getMultiSelectStartRowIndex) {
        positionToMove = 'head'
      } else {
        positionToMove = 'tail'
      }
    }

    if (direction === 'previous') {
      if (tailFieldIndex === getters.getMultiSelectStartFieldIndex) {
        positionToMove = 'head'
      } else {
        positionToMove = 'tail'
      }
    }

    if (direction === 'next') {
      if (headFieldIndex === getters.getMultiSelectStartFieldIndex) {
        positionToMove = 'tail'
      } else {
        positionToMove = 'head'
      }
    }

    dispatch('updateMultipleSelectIndexes', {
      position: positionToMove,
      rowIndex: positionToMove === 'tail' ? newRowTailIndex : newRowHeadIndex,
      fieldIndex:
        positionToMove === 'tail' ? newFieldTailIndex : newFieldHeadIndex,
    })

    return {
      position: positionToMove,
      rowIndex: positionToMove === 'tail' ? newRowTailIndex : newRowHeadIndex,
      fieldIndex:
        positionToMove === 'tail' ? newFieldTailIndex : newFieldHeadIndex,
    }
  },
  multiSelectHold({ getters, commit, dispatch }, { rowId, fieldIndex }) {
    if (getters.isMultiSelectHolding) {
      dispatch('setMultiSelectHeadOrTail', { rowId, fieldIndex })
    }
  },
  setMultiSelectHeadOrTail(
    { getters, commit, dispatch },
    { rowId, fieldIndex }
  ) {
    const { $registry, $client, $i18n, $config } = this
    commit('SET_SELECTED_CELL', { rowId: -1, fieldId: -1 })

    const rowIndex = getters.getRowIndexById(rowId)
    const startRowIndex = getters.getMultiSelectStartRowIndex
    const startFieldIndex = getters.getMultiSelectStartFieldIndex
    const newHeadRowIndex = Math.min(startRowIndex, rowIndex)
    const newHeadFieldIndex = Math.min(startFieldIndex, fieldIndex)
    const newTailRowIndex = Math.max(startRowIndex, rowIndex)
    const newTailFieldIndex = Math.max(startFieldIndex, fieldIndex)

    dispatch('updateMultipleSelectIndexes', {
      position: 'head',
      rowIndex: newHeadRowIndex,
      fieldIndex: newHeadFieldIndex,
    })

    dispatch('updateMultipleSelectIndexes', {
      position: 'tail',
      rowIndex: newTailRowIndex,
      fieldIndex: newTailFieldIndex,
    })

    commit('SET_MULTISELECT_ACTIVE', true)
  },
  correctMultiSelect({ getters, commit }) {
    const headRowIndex = getters.getMultiSelectHeadRowIndex
    const tailRowIndex = getters.getMultiSelectTailRowIndex
    const headFieldIndex = getters.getMultiSelectHeadFieldIndex
    const tailFieldIndex = getters.getMultiSelectTailFieldIndex
    const startRowIndex = getters.getMultiSelectStartRowIndex
    const startFieldIndex = getters.getMultiSelectStartFieldIndex

    const maxRowIndex = getters.getRowsLength + getters.getBufferStartIndex - 1
    const maxFieldIndex = getters.getNumberOfVisibleFields - 1

    if (headRowIndex > maxRowIndex || headFieldIndex > maxFieldIndex) {
      commit('CLEAR_AREA_SELECTION')
      commit('CLEAR_AREA_START_SELECTION')
      return
    }

    commit('UPDATE_MULTISELECT', {
      position: 'tail',
      rowIndex: tailRowIndex > maxRowIndex ? maxRowIndex : tailRowIndex,
      fieldIndex:
        tailFieldIndex > maxFieldIndex ? maxFieldIndex : tailFieldIndex,
    })

    const newStartRowIndex =
      startRowIndex > maxRowIndex ? maxRowIndex : startRowIndex
    const newStartFieldIndex =
      startFieldIndex > maxFieldIndex ? maxFieldIndex : startFieldIndex

    commit('SET_MULTISELECT_START_ROW_INDEX', newStartRowIndex)
    commit('SET_MULTISELECT_START_FIELD_INDEX', newStartFieldIndex)
  },
  /**
   * Returns the fields and rows necessaries to extract data from the selection.
   * It only contains the rows and fields selected by the multiple select.
   * If one or more rows are not in the buffer, they are fetched from the backend.
   */
  async getCurrentSelection({ dispatch, getters }, { fields }) {
    const { $registry, $client, $i18n, $config } = this
    const selectionType = getters.getSelectionType
    let rows = []
    let fieldsToUse = fields
    let fetchParams = null

    const allFieldsDataInBuffer = (rows, fields) => {
      return fields.every((field) => {
        const fieldType = $registry.get('field', field.type)
        return !fieldType.shouldRefetchFieldData(field, rows)
      })
    }

    if (selectionType === GRID_VIEW_MULTI_SELECT_CHECKBOX) {
      const selectedRows = getters.getCheckboxSelectedRows
      const allRowIds = getters.getAllRows.map((r) => r.id)
      const selectedRowIds = getters.getCheckboxSelectedRowsIds

      if (
        selectedRowIds.every((id) => allRowIds.includes(id)) &&
        allFieldsDataInBuffer(selectedRows, fields)
      ) {
        rows = selectedRows
      } else {
        fetchParams = {
          startIndex: 0,
          limit: $config.public.baserowRowPageSizeLimit,
          fields,
          rowIds: selectedRowIds,
          limitLinkedItems: LINKED_ITEMS_LOAD_ALL,
        }
      }
    } else {
      const [minFieldIndex, maxFieldIndex] =
        getters.getMultiSelectFieldIndexSorted
      fieldsToUse = fields.slice(minFieldIndex, maxFieldIndex + 1)

      if (
        getters.areMultiSelectRowsWithinBuffer &&
        allFieldsDataInBuffer(getters.getSelectedRows, fieldsToUse)
      ) {
        rows = getters.getSelectedRows
      } else {
        const [minRowIndex, maxRowIndex] = getters.getMultiSelectRowIndexSorted
        const limit = maxRowIndex - minRowIndex + 1
        fetchParams = {
          startIndex: minRowIndex,
          limit,
          fields: fieldsToUse,
        }
      }
    }

    if (fetchParams) {
      // Fetch rows from backend
      rows = await dispatch('fetchRowsByIndex', fetchParams)
    }

    return [fieldsToUse, rows]
  },
  /**
   * This function is called if a user attempts to access rows that are
   * no longer in the row buffer and need to be fetched from the backend.
   * A user can select some or all fields in a row, and only those fields
   * will be returned.
   */
  async fetchRowsByIndex(
    { getters, rootGetters, state },
    { startIndex, limit, fields, excludeFields, rowIds, limitLinkedItems }
  ) {
    const { $registry, $client, $i18n, $config } = this
    if (fields !== undefined) {
      fields = fields.map((field) => `field_${field.id}`)
    }
    if (excludeFields !== undefined) {
      excludeFields = excludeFields.map((field) => `field_${field.id}`)
    }

    const gridId = getters.getLastGridId
    const view = getViewOrFlatDefault(rootGetters, getters.getLastGridId)

    const ranges = getters.isGroupByMode
      ? getGroupByAbsoluteRangesForVisibleRange(
          getGroupByLayoutFromState(state),
          startIndex,
          limit
        )
      : [{ offset: startIndex, limit }]

    const results = []
    for (const range of ranges) {
      const { data } = await GridService($client).fetchRows({
        gridId,
        offset: range.offset,
        limit: range.limit,
        search: getters.getServerSearchTerm,
        searchMode: getDefaultSearchModeFromEnv($config),
        publicUrl: rootGetters['page/view/public/getIsPublic'],
        publicAuthToken: rootGetters['page/view/public/getAuthToken'],
        groupBy: getGroupBy(rootGetters, getters.getLastGridId),
        orderBy: getOrderBy(view, getters.getAdhocSorting),
        filters: getFilters(view, getters.getAdhocFiltering),
        includeFields: fields,
        excludeFields,
        excludeCount: getters.canExcludeCount,
        limitLinkedItems,
        rowIds,
      })
      results.push(...data.results)
    }
    return results
  },
  setRowHover({ commit }, { row, value }) {
    commit('SET_ROW_HOVER', { row, value })
  },
  /**
   * Adds a field with a provided value to the rows in memory.
   */
  addField({ commit }, { field, value = null }) {
    commit('ADD_FIELD_TO_ROWS_IN_BUFFER', { field, value })
  },
  /**
   * Adds a field to the list of selected fields of a row. We use this to indicate
   * if a row is selected or not.
   */
  addRowSelectedBy({ commit }, { row, field }) {
    commit('ADD_ROW_SELECTED_BY', { row, fieldId: field.id })
  },
  /**
   * Removes a field from the list of selected fields of a row. We use this to
   * indicate if a row is selected or not. If the field is not selected anymore
   * and it does not match the filters it can be removed from the store.
   */
  removeRowSelectedBy(
    { commit, dispatch },
    { grid, row, field, fields, getScrollTop, isRowOpenedInModal = undefined }
  ) {
    commit('REMOVE_ROW_SELECTED_BY', { row, fieldId: field.id })
    dispatch('refreshRow', {
      grid,
      row,
      fields,
      getScrollTop,
      isRowOpenedInModal,
    })
  },
  /**
   * Used when row data needs to be directly re-fetched from the Backend and
   * the other (background) row needs to be refreshed. For example, when editing
   * row from a *different* table using ForeignRowEditModal or just RowEditModal
   * component in general.
   */
  async refreshRowFromBackend(
    { commit, getters, rootGetters },
    { table, row }
  ) {
    const { $registry, $client, $i18n, $config } = this
    commit('SET_ROW_FETCHING', { row, value: true })
    try {
      const gridId = getters.getLastGridId
      const publicUrl = rootGetters['page/view/public/getIsPublic']
      const publicAuthToken = rootGetters['page/view/public/getAuthToken']
      const { data } = await ViewService($client).fetchRow(
        table.id,
        row.id,
        gridId,
        publicUrl,
        publicAuthToken
      )
      commit('UPDATE_ROW_IN_BUFFER', { row, values: data })
    } finally {
      commit('SET_ROW_FETCHING', { row, value: false })
    }
    // Use the return value to update the desired row with latest values from the
    // backend.
  },
  /**
   * Called when the user wants to create a new row. Optionally a `before` row
   * object can be provided which will forcefully add the row before that row. If no
   * `before` is provided, the row will be added last.
   */
  async createNewRow(
    { commit, getters, dispatch },
    {
      view,
      table,
      fields,
      values = {},
      before = null,
      groupPath = null,
      selectPrimaryCell = false,
      isRowOpenedInModal = undefined,
    }
  ) {
    const { $registry, $client, $i18n, $config } = this
    await dispatch('createNewRows', {
      view,
      table,
      fields,
      rows: [values],
      before,
      groupPath,
      selectPrimaryCell,
      isRowOpenedInModal,
    })
  },
  async createNewRowInGroup(
    { dispatch, getters },
    { view, table, fields, path, selectPrimaryCell = true }
  ) {
    const groupByFields = getGroupByFieldsFromActiveGroupBys(
      getters.getActiveGroupBys,
      fields
    )
    const values = groupPathDefaults(path, groupByFields, this.$registry)
    await dispatch('createNewRow', {
      view,
      table,
      fields,
      values,
      groupPath: path,
      selectPrimaryCell,
    })
  },
  async createNewRows(
    { commit, getters, dispatch, state },
    {
      view,
      table,
      fields,
      rows = {},
      before = null,
      groupPath = null,
      selectPrimaryCell = false,
      isRowOpenedInModal = undefined,
      undoRedoActionGroupId = null,
      skipFetchByScrollTop = false,
    }
  ) {
    const { $registry, $client, $i18n, $config } = this
    let keepSelectedWarningRowsInPlace = false
    const taskQueue = createAndUpdateRowQueue.getOrCreateQueue(
      `table_${table.id}`
    )
    const taskId = taskQueue.add(async () => {
      const fieldNewRowValueMap = buildNewRowDefaults({
        view,
        fields,
        registry: $registry,
      })

      const step = before ? ORDER_STEP_BEFORE : ORDER_STEP

      // If before is not provided, then the row is added last. Because we don't know
      // the total amount of rows in the table, we are going to add find the highest
      // existing order in the buffer and increase that by one.
      let order = getters.getHighestOrder
        .integerValue(BigNumber.ROUND_CEIL)
        .plus(step)
        .toString()
      if (before !== null) {
        // It's okay to temporary set an order that just subtracts the
        // ORDER_STEP_BEFORE because there will never be a conflict with rows because
        // of the fraction ordering.
        order = new BigNumber(before.order)
          .minus(new BigNumber(step * rows.length))
          .toString()
      }

      const index =
        before === null
          ? getters.getBufferEndIndex
          : getters.getAllRows.findIndex((r) => r.id === before.id)

      const fieldPermissionsMap = fields.reduce((map, field) => {
        const fieldType = $registry.get('field', field._.type.type)
        map[`field_${field.id}`] = fieldType.canWriteFieldValues(field)
        return map
      }, {})
      const rowsPopulated = rows.map((row) => {
        // Exclude fields where the user does not have the permission to edit
        const permittedValues = Object.entries(row).reduce(
          (map, [key, value]) => {
            if (fieldPermissionsMap[key] === true) {
              map[key] = value
            }
            return map
          },
          {}
        )
        row = { ...clone(fieldNewRowValueMap), ...permittedValues }
        row = populateRow(row)
        row.id = uuid()
        row.order = order
        row._.loading = true

        order = new BigNumber(order).plus(new BigNumber(step)).toString()

        return row
      })

      const isSingleRowInsertion = rowsPopulated.length === 1
      const oldCount = getters.getCount
      const isGroupByInsertion =
        getters.isGroupByMode && groupPath !== null && isSingleRowInsertion
      const optimisticGroupByTreePaths = []
      const insertRowIntoGroupBySection = ({
        row,
        path = null,
        appendToPath = false,
      }) => {
        const { groupByFields, location } = resolveGroupByInsertLocation(
          { getters, state, registry: $registry },
          { row, view, fields }
        )
        const rowPath = path ?? location.path
        const sectionKey =
          path === null ? location.sectionKey : pathKey(path, groupByFields)
        let position = location.position

        if (appendToPath) {
          const section = findGroupByRowSection(
            getters.getGroupByLayout,
            sectionKey,
            groupByFields
          )
          position =
            section?.rowCount ??
            state.groupBy.sectionRows[sectionKey]?.length ??
            0
        }

        commit('UPDATE_GROUP_BY_TREE_PATH_COUNT', {
          path: rowPath,
          fields: groupByFields,
          delta: 1,
          registry: $registry,
        })
        optimisticGroupByTreePaths.push({
          path: rowPath,
          fields: groupByFields,
        })
        commit('INSERT_ROW_AT_LOCATION', {
          sectionKey,
          position,
          row,
        })
        commit('SET_COUNT', getters.getCount + 1)
      }
      const canUpdateOptimistically = canRowsBeOptimisticallyUpdatedInView(
        $registry,
        view,
        fields,
        getters.getActiveSearchTerm
      )
      if (isGroupByInsertion) {
        insertRowIntoGroupBySection({
          row: rowsPopulated[0],
          path: groupPath,
          appendToPath: true,
        })
      } else if (canUpdateOptimistically) {
        // When a single row is inserted we don't want to deal with filters, sorts and
        // search just yet. Therefore it is okay to just insert the row into the buffer.
        if (isSingleRowInsertion) {
          if (getters.isGroupByMode) {
            insertRowIntoGroupBySection({ row: rowsPopulated[0] })
          } else {
            commit('INSERT_NEW_ROWS_IN_BUFFER_AT_INDEX', {
              rows: rowsPopulated,
              index,
            })
          }
        } else {
          // When inserting multiple rows we will need to deal with filters, sorts or search
          // not matching. `createdNewRow` deals with exactly that for us.
          for (const rowPopulated of rowsPopulated) {
            await dispatch('createdNewRow', {
              view,
              fields,
              values: rowPopulated,
              metadata: {},
              populate: false,
            })
          }
        }
      } else {
        // just insert rows in the buffer and delay dealing with filters, sorts or search
        // until we get the response from the backend.
        commit('INSERT_NEW_ROWS_IN_BUFFER_AT_INDEX', {
          rows: rowsPopulated,
          index,
        })
      }

      dispatch('visibleByScrollTop')

      // Check if not all rows are visible.
      const diff = oldCount - getters.getCount + rowsPopulated.length
      if (!isSingleRowInsertion && diff > 0) {
        dispatch(
          'toast/success',
          {
            title: $i18n.t('gridView.hiddenRowsInsertedTitle'),
            message: $i18n.t('gridView.hiddenRowsInsertedMessage', {
              number: diff,
            }),
          },
          { root: true }
        )
      }

      const primaryField = fields.find((f) => f.primary)
      if (selectPrimaryCell && primaryField && isSingleRowInsertion) {
        await dispatch('setSelectedCell', {
          rowId: rowsPopulated[0].id,
          fieldId: primaryField.id,
          fields,
        })
      }

      if (
        canUpdateOptimistically &&
        isSingleRowInsertion &&
        viewHasRulesThatCanMoveOrHideRows(
          {
            ...view,
            group_bys: isGroupByInsertion ? [] : view.group_bys,
          },
          getters.getActiveSearchTerm
        )
      ) {
        await dispatch('onRowChange', {
          view,
          row: rowsPopulated[0],
          fields,
        })
      }

      // The backend expects slightly different values than what we have in the row
      // buffer. Therefore, we need to prepare the rows before we can send them to the
      // backend.
      const rowsPrepared = rows.map((row) => {
        row = { ...clone(fieldNewRowValueMap), ...row }
        row = prepareRowForRequest(row, fields, $registry)
        return row
      })

      // Lock the newly created rows with their persistent ID, so that if the user
      // changes the value before the row is created, that request is queued.
      rowsPopulated.forEach((row) => {
        createAndUpdateRowQueue.lock(row._.persistentId)
      })

      try {
        let data = {}
        // We're queueing this task, so other tasks, that may read state and modify it,
        // won't overalp.

        const resp = await RowService($client).batchCreate(
          table.id,
          rowsPrepared,
          before !== null ? before.id : null,
          undoRedoActionGroupId,
          getters.getLastGridId
        )
        data = resp.data
        const updatedFieldIds = data.metadata?.updated_field_ids || []
        const fieldsToFinalize = fields
          .filter(
            (field) =>
              $registry.get('field', field.type).isReadOnlyField(field) ||
              updatedFieldIds.includes(field.id)
          )
          .map((field) => `field_${field.id}`)
        commit('FINALIZE_ROWS_IN_BUFFER', {
          oldRows: rowsPopulated,
          newRows: data.items,
          fields: fieldsToFinalize,
        })

        for (let i = 0; i < data.items.length; i += 1) {
          const item = data.items[i]
          // Use the updated row in the buffer if it exists, otherwise use the populated
          // row object to update inner state.
          const row = getters.getRow(item.id) || rowsPopulated[i]
          dispatch('onRowChange', { view, row, fields })
          const rowId = row.id
          // Get the latest row so that any changes that might have been made in the
          // meantime are included. This is needed to pass the correct row into the
          // `refreshRow` that shows/hide the row.
          const latestRow = getters.getRow(rowId)
          if (latestRow?._.selected && rowHasViewWarning(latestRow)) {
            keepSelectedWarningRowsInPlace = true
          }
          if (latestRow && !latestRow._.selected) {
            dispatch('refreshRow', {
              grid: view,
              row: latestRow,
              fields,
              isRowOpenedInModal,
            })
          }
        }

        await dispatch('fetchAllFieldAggregationData', {
          view,
        })
      } catch (error) {
        if (isSingleRowInsertion) {
          const rowStillInBuffer = getters.getRow(rowsPopulated[0].id)
          if (rowStillInBuffer && optimisticGroupByTreePaths.length > 0) {
            optimisticGroupByTreePaths.forEach(
              ({ path, fields: groupByFields }) => {
                commit('UPDATE_GROUP_BY_TREE_PATH_COUNT', {
                  path,
                  fields: groupByFields,
                  delta: -1,
                  registry: $registry,
                })
              }
            )
          }
          if (rowStillInBuffer) {
            commit('DELETE_ROW_IN_BUFFER', rowsPopulated[0])
          }
        } else {
          // When we have multiple rows we will need to re-evaluate where the rest of the
          // rows are now positioned. Therefore, we need to call `deletedExistingRow` to
          // deal with all the potential edge cases
          for (const rowPopulated of rowsPopulated) {
            await dispatch('deletedExistingRow', {
              view,
              fields,
              row: rowPopulated,
            })
          }
        }
        throw error
      } finally {
        // Release the lock because now the update requests can come through if they
        // were made. Even if the rows were not created, we have to release the ids to
        // clear the memory.

        rowsPopulated.forEach((row) => {
          createAndUpdateRowQueue.release(row._.persistentId)
        })
      }
    })
    await taskQueue.waitFor(taskId)

    if (!skipFetchByScrollTop && !keepSelectedWarningRowsInPlace) {
      dispatch('fetchByScrollTopDelayed', {
        scrollTop: getters.getScrollTop,
        fields,
      })
    }
  },
  /**
   * Called after a new row has been created, which could be by the user or via
   * another channel. It will only add the row if it belongs inside the views and it
   * also makes sure that row will be inserted at the correct position.
   */
  async createdNewRow(
    { commit, getters, dispatch, state },
    { view, fields, values, metadata, populate = true }
  ) {
    if (getters.getRowIndexById(values.id) !== -1) {
      return
    }

    const { $registry } = this
    const row = clone(values)

    if (populate) {
      populateRow(row, metadata)
    }

    // The lifecycle helper only evaluates filters/sortings, so the search match
    // is still gated here against the active search term.
    await dispatch('updateSearchMatchesForRow', { row, fields })
    if (!row._.matchSearch) {
      return
    }

    handleRowCreated({
      context: createRowLifecycleContext({
        registry: $registry,
        view,
        fields,
        groupBys: view.group_bys,
      }),
      mutations: {
        insertAtPosition: (insertedRow, { sortedIndex, isFirst, isLast }) => {
          if (getters.isGroupByMode) {
            const { groupByFields, location } = resolveGroupByInsertLocation(
              { getters, state, registry: $registry },
              { row: insertedRow, view, fields }
            )
            commit('UPDATE_GROUP_BY_TREE_PATH_COUNT', {
              path: location.path,
              fields: groupByFields,
              delta: 1,
              registry: $registry,
            })
            commit('INSERT_ROW_AT_LOCATION', {
              sectionKey: location.sectionKey,
              position: location.position,
              row: insertedRow,
            })
            commit('SET_COUNT', getters.getCount + 1)
            return
          }

          const inBuffer =
            (isFirst && getters.getBufferStartIndex === 0) ||
            (isLast && getters.getBufferEndIndex === getters.getCount) ||
            (!isFirst && !isLast)
          if (inBuffer) {
            commit('INSERT_NEW_ROWS_IN_BUFFER_AT_INDEX', {
              rows: [insertedRow],
              index: sortedIndex,
            })
          } else {
            if (isFirst) {
              commit('SET_BUFFER_START_INDEX', getters.getBufferStartIndex + 1)
            }
            commit('SET_COUNT', getters.getCount + 1)
          }
        },
        applyMatchFlags: (rowId, { matchFilters, matchSortings }) => {
          commit('SET_ROW_MATCH_FILTERS', { row, value: matchFilters })
          commit('SET_ROW_MATCH_SORTINGS', { row, value: matchSortings })
        },
        rowsForMatchCheck: () => getters.getAllRows,
      },
      row,
    })
  },
  /**
   * Moves an existing row to the position before the provided before row. It will
   * update the order and makes sure that the row is inserted in the correct place.
   * A call to the backend will also be made to update the order persistent.
   */
  async moveRow(
    { commit, dispatch, getters },
    { table, grid, fields, getScrollTop, row, before = null }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const oldOrder = row.order

    // If before is not provided, then the row is added last. Because we don't know
    // the total amount of rows in the table, we are going to add find the highest
    // existing order in the buffer and increase that by one.
    let order = getters.getHighestOrder
      .integerValue(BigNumber.ROUND_CEIL)
      .plus('1')
      .toString()
    if (before !== null) {
      // If the row has been placed before another row we can specifically insert to
      // the row at a calculated index.
      const change = new BigNumber(ORDER_STEP_BEFORE)
      // It's okay to temporary set an order that just subtracts the
      // ORDER_STEP_BEFORE because there will never be a conflict with rows because
      // of the fraction ordering.
      order = new BigNumber(before.order).minus(change).toString()
    }

    // In order to make changes feel really fast, we optimistically
    // updated all the field values that provide a onRowMove function
    const fieldsToCallOnRowMove = fields
    const optimisticFieldValues = {}
    const valuesBeforeOptimisticUpdate = {}

    fieldsToCallOnRowMove.forEach((field) => {
      const fieldType = $registry.get('field', field._.type.type)
      const fieldID = `field_${field.id}`
      const currentFieldValue = row[fieldID]
      const fieldValue = fieldType.onRowMove(
        row,
        order,
        oldOrder,
        field,
        currentFieldValue
      )
      if (currentFieldValue !== fieldValue) {
        optimisticFieldValues[fieldID] = fieldValue
        valuesBeforeOptimisticUpdate[fieldID] = currentFieldValue
      }
    })

    dispatch('updatedExistingRow', {
      view: grid,
      fields,
      row,
      values: { order, ...optimisticFieldValues },
    })

    try {
      const { data } = await RowService($client).move(
        table.id,
        row.id,
        before !== null ? before.id : null
      )
      // Use the return value to update the moved row with values from
      // the backend
      commit('UPDATE_ROW_IN_BUFFER', { row, values: data })
      if (before === null) {
        // Not having a before means that the row was moved to the end and because
        // that order was just an estimation, we want to update it with the real
        // order, otherwise there could be order conflicts in the future.
        commit('UPDATE_ROW_IN_BUFFER', { row, values: { order: data.order } })
      }
      dispatch('fetchByScrollTopDelayed', {
        scrollTop: getScrollTop(),
        fields,
      })
      dispatch('fetchAllFieldAggregationData', { view: grid })
    } catch (error) {
      dispatch('updatedExistingRow', {
        view: grid,
        fields,
        row,
        values: { order: oldOrder, ...valuesBeforeOptimisticUpdate },
      })
      throw error
    }
  },
  /**
   * Updates a grid view field value. It will immediately be updated in the store
   * and only if the change request fails it will revert to give a faster
   * experience for the user.
   */
  async updateRowValue(
    { commit, dispatch, getters },
    {
      table,
      view,
      row,
      field,
      fields,
      value,
      oldValue,
      isRowOpenedInModal = undefined,
    }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const taskQueue = createAndUpdateRowQueue.getOrCreateQueue(
      `table_${table.id}`
    )
    const { newRowValues, oldRowValues, updateRequestValues } =
      prepareNewOldAndUpdateRequestValues(
        row,
        fields,
        field,
        value,
        oldValue,
        $registry
      )
    const canUpdateOptimistically = canRowsBeOptimisticallyUpdatedInView(
      $registry,
      view,
      fields,
      getters.getActiveSearchTerm
    )
    const hasViewRulesThatCanMoveOrHideRows = viewHasRulesThatCanMoveOrHideRows(
      view,
      getters.getActiveSearchTerm
    )

    // Apply the changed field value immediately only when it cannot affect row
    // visibility or position. Grouped/sorted/filtered views need the queued
    // lifecycle path below, while the old row values are still intact.
    // The PATCH and all other side-effects still run inside the task queue.
    if (canUpdateOptimistically && !hasViewRulesThatCanMoveOrHideRows) {
      const storeRow = getters.getRow(row.id)
      if (storeRow !== undefined) {
        commit('UPDATE_ROW_FIELD_VALUE', { row: storeRow, field, value })
      }
    }

    const taskId = taskQueue.add(async () => {
      // This task may have been queued behind a still-pending create for the same
      // row (the queue is keyed by persistentId). By the time it runs, that create
      // has finalized the row's temporary id into its persisted id, mutating the
      // buffer row in place. The value objects were prepared with the id captured
      // at call time, so re-stamp them with the row's current id; otherwise the
      // PATCH would target the now-stale temporary id (404 + rollback) and the
      // optimistic commits would reset the row's id back to the temporary one.
      newRowValues.id = row.id
      oldRowValues.id = row.id
      updateRequestValues.id = row.id

      /**
       * This helper function will make sure that the values of the related row are
       * updated the right way.
       */
      const updateValues = async (row, values, optimisticUpdate) => {
        const rowExistsInBuffer = getters.getRow(row.id) !== undefined

        if (rowExistsInBuffer) {
          const isSelected =
            (getters.getRow(row.id)?._?.selectedBy?.length ?? 0) > 0
          if (
            optimisticUpdate &&
            hasViewRulesThatCanMoveOrHideRows &&
            !isSelected
          ) {
            await dispatch('updatedExistingRow', {
              view,
              fields,
              row,
              values,
            })
          } else {
            // Show the typed value immediately. While the edited row is still selected
            // (the user is editing it) we keep it visible with a match warning instead
            // of moving/removing it; the actual move/remove/regroup is deferred to
            // deselect (refreshRow, which is selected-aware) or backend confirmation,
            // per the grid-view-test-plan contract (2.2.1a / 2.2.7a / 2.3.1a).
            // Unselected optimistic edits still reconcile immediately above.
            commit('UPDATE_ROW_VALUES', {
              row,
              values: { ...values },
            })
            if (optimisticUpdate) {
              await dispatch('onRowChange', { view, row, fields })
            }
          }
        } else {
          // If the row doesn't exist in the buffer, it could be that the new values
          // bring in into there. Dispatching the `updatedExistingRow` will make
          // sure that will happen in the right way.
          await dispatch('updatedExistingRow', { view, fields, row, values })
          // There is a chance that the row is not in the buffer, but it does exist in
          // the view. In that case, the `updatedExistingRow` action has not done
          // anything. There is a possibility that the row is visible in the row edit
          // modal, but then it won't be updated, so we have to update it forcefully.
          commit('UPDATE_ROW_VALUES', {
            row,
            values: { ...values },
          })
          await dispatch('fetchByScrollTopDelayed', {
            scrollTop: getters.getScrollTop,
            fields,
          })
        }
      }

      if (!canUpdateOptimistically) {
        commit('SET_ROW_LOADING', { row, value: true })
      }

      // When possible update the values before making a request to the backend to make
      // it feel instant for the user. If we can't safely do it in the frontend, then
      // we have to show a loading state and update the row after the request has been
      // made.
      await updateValues(row, newRowValues, canUpdateOptimistically)
      try {
        const batchResponse = await RowService($client).batchUpdate(
          table.id,
          [updateRequestValues],
          null,
          getters.getLastGridId
        )

        const updatedRows = []
          .concat(batchResponse.data.items)
          .concat(batchResponse.data.metadata?.cascade_update?.rows || [])

        const updatedFieldIds =
          batchResponse.data.metadata?.updated_field_ids || []

        const otherFieldsChangedInBackend = !_.isEqual(updatedFieldIds, [
          field.id,
        ])

        for (const updatedRowData of updatedRows) {
          // Extract only the read-only values because we don't want to update the other
          // values that might have been updated in the meantime.
          const rowData = extractChangedFields(
            updatedRowData,
            fields,
            updatedFieldIds,
            $registry
          )

          // The backend may update rows that are not in the current buffer.
          // In that case, the row will be `undefined`, and we don't need to
          // update it.
          const existing = getters.getRow(rowData.id)
          if (existing === undefined) {
            continue
          }
          // Update the remaining values like formula, which depend on the backend.
          await updateValues(existing, rowData, true)

          // If we can't optimistically update the row, refresh it to stop the loading
          // state, show proper messages, and update its position and state. Also, if the
          // backend changed other fields, we should refresh sorting/search/filtering.
          if (
            !canUpdateOptimistically ||
            otherFieldsChangedInBackend ||
            hasViewRulesThatCanMoveOrHideRows
          ) {
            commit('SET_ROW_LOADING', { row: existing, value: false })
            const refreshUnselectedRow = () => {
              // Get the latest row so that updated `readOnlyData` values are included,
              // and any other changes that might have been made in the meantime. This is
              // needed to pass the correct row into the `refreshRow` that shows/hide the
              // row.
              const row = getters.getRow(existing.id)
              if (row && !row._.selected) {
                dispatch('refreshRow', {
                  grid: view,
                  row,
                  fields,
                  isRowOpenedInModal,
                })
              }
            }

            if (hasViewRulesThatCanMoveOrHideRows) {
              refreshUnselectedRow()
            } else {
              setTimeout(refreshUnselectedRow, REFRESH_ROW_DELAY_MS)
            }
          }
        }
        dispatch('fetchAllFieldAggregationData', {
          view,
        })
      } catch (error) {
        if (!canUpdateOptimistically) {
          commit('SET_ROW_LOADING', { row, value: false })
        }
        await updateValues(row, oldRowValues, true)
        const latestRow = getters.getRow(row.id)
        if (latestRow && hasViewRulesThatCanMoveOrHideRows) {
          await dispatch('refreshRow', {
            grid: view,
            row: latestRow,
            fields,
            isRowOpenedInModal,
          })
        }
        throw error
      }
    }, row._.persistentId)
    await taskQueue.waitFor(taskId)
  },
  /**
   * Set the multiple select indexes using the row and field head and tail indexes.
   */
  setMultipleSelect(
    { commit, dispatch },
    { rowHeadIndex, fieldHeadIndex, rowTailIndex, fieldTailIndex }
  ) {
    const { $registry, $client, $i18n, $config } = this
    dispatch('setSelectionType', { selectionType: GRID_VIEW_MULTI_SELECT_AREA })
    dispatch('updateMultipleSelectIndexes', {
      position: 'head',
      rowIndex: rowHeadIndex,
      fieldIndex: fieldHeadIndex,
    })
    dispatch('updateMultipleSelectIndexes', {
      position: 'tail',
      rowIndex: rowTailIndex,
      fieldIndex: fieldTailIndex,
    })
    commit('SET_MULTISELECT_ACTIVE', true)
    commit('SET_SELECTED_CELL', { rowId: -1, fieldId: -1 })
  },
  /**
   * Action to update head or tail (position) indexes for row and field
   * multiple select operations.
   *
   * It will prevent updating selection to nonsense indexes by doing nothing
   * if a provided index isn't correct.
   */
  updateMultipleSelectIndexes(
    { commit, getters },
    { position, rowIndex, fieldIndex }
  ) {
    const { $registry, $client, $i18n, $config } = this
    if (
      (position === 'tail' && getters.getMultiSelectHeadRowIndex !== -1) ||
      (position === 'head' && getters.getMultiSelectTailRowIndex !== -1)
    ) {
      // check if the selection would go over limit
      const limit = $config.public.baserowRowPageSizeLimit
      const previousIndex =
        position === 'head'
          ? getters.getMultiSelectTailRowIndex
          : getters.getMultiSelectHeadRowIndex
      if (Math.abs(previousIndex - rowIndex) > limit - 1) {
        if (rowIndex > previousIndex) {
          rowIndex = previousIndex + limit - 1
        } else {
          rowIndex = previousIndex - limit + 1
        }
      }
    }

    if (rowIndex < 0 || fieldIndex < 0) {
      return
    }

    if (
      rowIndex > getters.getRowsLength + getters.getBufferStartIndex - 1 ||
      fieldIndex > getters.getNumberOfVisibleFields - 1
    ) {
      return
    }

    commit('UPDATE_MULTISELECT', {
      position,
      rowIndex,
      fieldIndex,
    })
  },
  /**
   * This action is used by the grid view to change multiple cells when pasting
   * multiple values. It figures out which cells need to be changed, makes a request
   * to the backend and updates the affected rows in the store.
   */
  async updateDataIntoCells(
    { getters, commit, dispatch },
    {
      table,
      view,
      allVisibleFields,
      allFieldsInTable,
      getScrollTop,
      textData,
      jsonData,
      rowIndex,
      fieldIndex,
      selectUpdatedCells = true,
    }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const copiedRowsCount = textData.length
    const copiedCellsInRowsCount = textData[0].length
    const isSingleCellCopied =
      copiedRowsCount === 1 && copiedCellsInRowsCount === 1

    const selectedRowsCount =
      getters.getMultiSelectTailRowIndex -
      getters.getMultiSelectHeadRowIndex +
      1
    const selectedFieldsCount =
      getters.getMultiSelectTailFieldIndex -
      getters.getMultiSelectHeadFieldIndex +
      1

    const isSingleRowCopied = copiedRowsCount === 1 && selectedRowsCount > 1

    if (isSingleCellCopied) {
      // the textData and jsonData are recreated
      // to fill the entire multi selection

      const rowTextArray = Array(selectedFieldsCount).fill(textData[0][0])
      textData = Array(selectedRowsCount).fill(rowTextArray)

      if (jsonData) {
        const rowJsonArray = Array(selectedFieldsCount).fill(jsonData[0][0])
        jsonData = Array(selectedRowsCount).fill(rowJsonArray)
      }
    } else if (isSingleRowCopied) {
      textData = Array(selectedRowsCount).fill(textData[0])
      if (jsonData) {
        jsonData = Array(selectedRowsCount).fill(jsonData[0])
      }
    }

    // If the origin row and field index are not provided, we need to use the
    // head indexes of the multiple select.
    const rowHeadIndex = rowIndex ?? getters.getMultiSelectHeadRowIndex
    const fieldHeadIndex = fieldIndex ?? getters.getMultiSelectHeadFieldIndex

    // Based on the data, we can figure out in which cells we must paste. Here we find
    // the maximum tail indexes.
    let rowTailIndex =
      Math.min(getters.getCount, rowHeadIndex + copiedRowsCount) - 1
    let fieldTailIndex =
      Math.min(
        allVisibleFields.length,
        fieldHeadIndex + copiedCellsInRowsCount
      ) - 1

    if (isSingleCellCopied || isSingleRowCopied) {
      // we want the tail indexes to follow the multi select exactly
      rowTailIndex = getters.getMultiSelectTailRowIndex
      fieldTailIndex = getters.getMultiSelectTailFieldIndex
    }

    if (
      !(isSingleCellCopied || isSingleRowCopied) &&
      selectUpdatedCells &&
      !(view.sortings || view.group_bys || view.filters)
    ) {
      // Expand the selection of the multiple select to the cells that we're going to
      // paste in, so the user can see which values have been updated. This is because
      // it could be that there are more or less values in the clipboard compared to
      // what was originally selected.
      // However, we should not mark multiple rows as selected if the view has
      // any filtering/sorting/grouping by, as rows pasted may be scattered/hidden
      // in the view. Multiselect will not show correct contents then, and we can't
      // select disjoined rows.
      await dispatch('setMultipleSelect', {
        rowHeadIndex,
        fieldHeadIndex,
        rowTailIndex,
        fieldTailIndex,
      })
    }

    const newRowsCount = copiedRowsCount - (rowTailIndex - rowHeadIndex + 1)
    const textDataToCreate = textData.slice(copiedRowsCount - newRowsCount)
    const jsonDataToCreate = jsonData
      ? jsonData.slice(copiedRowsCount - newRowsCount)
      : undefined

    // Figure out which rows are already in the buffered and temporarily store them
    // in an array.
    const fieldsInOrder = allVisibleFields.slice(
      fieldHeadIndex,
      fieldTailIndex + 1
    )
    let rowsInOrder = getters.getAllRows.slice(
      rowHeadIndex - getters.getBufferStartIndex,
      rowTailIndex + 1 - getters.getBufferStartIndex
    )

    // Check if there are fields that can be updated. If there aren't any fields,
    // maybe because the provided index is outside of the available fields or
    // because there are only read only fields, we don't want to do anything.
    const writeFields = fieldsInOrder.filter((field) =>
      $registry.get('field', field.type).canWriteFieldValues(field)
    )
    if (writeFields.length === 0) {
      return
    }

    // Calculate if there are rows outside of the buffer that need to be fetched and
    // prepended or appended to the `rowsInOrder`
    let startIndex = rowHeadIndex
    if (rowHeadIndex + rowsInOrder.length >= getters.getBufferStartIndex) {
      startIndex += rowsInOrder.length
    }
    const limit = rowTailIndex - rowHeadIndex - rowsInOrder.length + 1
    if (limit > 0) {
      const rowsNotInBuffer = await dispatch('fetchRowsByIndex', {
        startIndex,
        limit,
      })
      // Depends on whether the missing rows are before or after the buffer.
      rowsInOrder =
        startIndex < getters.getBufferStartIndex
          ? [...rowsNotInBuffer, ...rowsInOrder]
          : [...rowsInOrder, ...rowsNotInBuffer]
    }

    // before populating existing rows with new values and calling RowService,
    // ensure no createRows is running. There can be a parallel createRows action
    // performing another request to create those rows in the backend.
    // If we call RowService too soon here, we'll send placeholder .id values (uuid)
    // to a PATCH operation.
    const taskQueue = createAndUpdateRowQueue.getOrCreateQueue(
      `table_${table.id}`
    )
    await taskQueue.waitAll()

    // Create a copy of the existing (old) rows, which are needed to create the
    // comparison when checking if the rows still matches the filters and position.
    const oldRowsInOrder = clone(rowsInOrder)

    // Prepare the values for update and update the row objects. The resulting list
    // of objects will be send to the backend.
    const valuesForUpdate = populateRows({
      tsvData: textData.slice(0, rowsInOrder.length),
      jsonData: jsonData ? jsonData.slice(0, rowsInOrder.length) : null,
      fieldsInOrder,
      registry: $registry,
      fromRows: rowsInOrder,
    })

    // We don't have to update the rows in the buffer before the request is being made
    // because we're showing a loading animation to the user indicating that the
    // rows are being updated.
    const undoRedoActionGroupId = createNewUndoRedoActionGroupId()
    const { data: responseData } = await RowService($client).batchUpdate(
      table.id,
      valuesForUpdate,
      undoRedoActionGroupId,
      getters.getLastGridId
    )
    const updatedRows = responseData.items
    // Create extra missing rows
    if (newRowsCount > 0) {
      await dispatch('createNewRows', {
        view,
        table,
        fields: allFieldsInTable,
        rows: populateRows({
          tsvData: textDataToCreate,
          jsonData: jsonDataToCreate,
          fieldsInOrder,
          registry: $registry,
          forUpdate: false,
        }),
        selectPrimaryCell: false,
        undoRedoActionGroupId,
        skipFetchByScrollTop: true,
      })
    }
    // Loop over the old rows, find the matching updated row and update them in the
    // buffer accordingly.
    for (const row of oldRowsInOrder) {
      // The values are the updated row returned by the response.
      const values = updatedRows.find((updatedRow) => updatedRow.id === row.id)
      // Calling the updatedExistingRow will automatically remove the row from the
      // view if it doesn't matter the filters anymore and it will also be moved to
      // the right position if changed.
      await dispatch('updatedExistingRow', {
        view,
        fields: allFieldsInTable,
        row,
        values,
        undoRedoActionGroupId,
      })
    }

    // Must be called because rows could have been removed or moved to a different
    // position and we might need to fetch missing rows.
    await dispatch('fetchByScrollTopDelayed', {
      scrollTop: getScrollTop(),
      fields: allFieldsInTable,
    })
    dispatch('fetchAllFieldAggregationData', { view })
  },
  /**
   * Called after an existing row has been updated, which could be by the user or
   * via another channel. It will make sure that the row has the correct position or
   * that is will be deleted or created depending if was already in the view.
   */
  async updatedExistingRow(
    { commit, getters, dispatch, state },
    { view, fields, row, values, metadata, updatedFieldIds = [] }
  ) {
    const { $registry } = this
    const oldRow = clone(row)
    const newRow = Object.assign(clone(row), values)
    populateRow(oldRow, metadata)
    populateRow(newRow, metadata)

    // The lifecycle helper only evaluates filters/sortings, so the search match
    // is still gated here against the active search term. A row that fails the
    // active search is effectively out of the view regardless of its filters.
    await dispatch('updateSearchMatchesForRow', { row: oldRow, fields })
    await dispatch('updateSearchMatchesForRow', { row: newRow, fields })

    const oldMatchesSearch = oldRow._.matchSearch
    const newMatchesSearch = newRow._.matchSearch
    const oldFlags = computeRowMatchFlags({
      row: oldRow,
      view,
      fields,
      registry: $registry,
      rowsInSortingGroup: getters.getAllRows,
      groupBys: view.group_bys,
    })
    const rowsExcludingNew = getters.getAllRows.filter(
      (r) => r.id !== newRow.id
    )
    const newFlags = computeRowMatchFlags({
      row: newRow,
      view,
      fields,
      registry: $registry,
      rowsInSortingGroup: rowsExcludingNew,
      groupBys: view.group_bys,
    })
    const oldRowExists = oldMatchesSearch && oldFlags.matchFilters
    const newRowExists = newMatchesSearch && newFlags.matchFilters
    const getFieldId = (key) => parseInt(key.split('_')[1])
    const clearPendingFieldOperations = () => {
      const fieldIdsToClearPendingOperationsFor = Object.entries(values)
        .filter(
          ([key, value]) =>
            key.startsWith('field_') &&
            (_.isEqual(value, oldRow[key]) ||
              updatedFieldIds.includes(getFieldId(key)))
        )
        .map(([key]) => getFieldId(key))

      commit('CLEAR_PENDING_FIELD_OPERATIONS', {
        fieldIds: fieldIdsToClearPendingOperationsFor,
        rowId: row.id,
      })
    }

    if (!oldRowExists && !newRowExists) {
      return
    }

    // When the row crosses the view boundary, delegate to the create/delete paths
    // so filter/search checks and group-by metadata updates stay aligned.
    if (oldRowExists && !newRowExists) {
      await dispatch('deletedExistingRow', { view, fields, row })
      return
    }
    if (!oldRowExists && newRowExists) {
      const materializedRow = getters.getRow(newRow.id)
      if (materializedRow) {
        commit('UPDATE_ROW_IN_BUFFER', {
          row: materializedRow,
          values,
          metadata,
        })
        await dispatch('onRowChange', { view, row: materializedRow, fields })
        clearPendingFieldOperations()
        return
      }
      await dispatch('createdNewRow', {
        view,
        fields,
        values: newRow,
        metadata,
      })
      return
    }

    if (getters.isGroupByMode) {
      const groupByFields = getGroupByFieldsFromActiveGroupBys(
        getters.getActiveGroupBys,
        fields
      )
      const oldPath = groupPathFromRow(oldRow, groupByFields, $registry)
      const newPath = groupPathFromRow(newRow, groupByFields, $registry)
      if (pathKey(oldPath, groupByFields) !== pathKey(newPath, groupByFields)) {
        commit('UPDATE_GROUP_BY_TREE_PATH_COUNT', {
          path: oldPath,
          fields: groupByFields,
          delta: -1,
          registry: $registry,
        })
        commit('UPDATE_GROUP_BY_TREE_PATH_COUNT', {
          path: newPath,
          fields: groupByFields,
          delta: 1,
          registry: $registry,
        })
      }
    }

    if (
      getters.getAllRows.findIndex(
        (r) => r.id !== newRow.id && r.order === newRow.order
      ) > -1
    ) {
      commit('DECREASE_ORDERS_IN_BUFFER_LOWER_THAN', newRow.order)
    }

    const insertAtPosition = (
      insertedRow,
      { sortedIndex, isFirst, isLast }
    ) => {
      if (getters.isGroupByMode) {
        const { location } = resolveGroupByInsertLocation(
          { getters, state, registry: $registry },
          { row: insertedRow, view, fields }
        )
        commit('INSERT_ROW_AT_LOCATION', {
          sectionKey: location.sectionKey,
          position: location.position,
          row: insertedRow,
        })
        return
      }

      const inBuffer =
        (isFirst && getters.getBufferStartIndex === 0) ||
        (isLast && getters.getBufferEndIndex === getters.getCount) ||
        (!isFirst && !isLast)
      if (inBuffer) {
        commit('INSERT_NEW_ROWS_IN_BUFFER_AT_INDEX', {
          rows: [insertedRow],
          index: sortedIndex,
        })
      } else {
        if (isFirst) {
          commit('SET_BUFFER_START_INDEX', getters.getBufferStartIndex + 1)
        }
        commit('SET_COUNT', getters.getCount + 1)
      }
    }

    const remove = (rowId) => {
      const allRows = getters.getAllRows
      const idx = allRows.findIndex((r) => r.id === rowId)
      if (idx >= 0) {
        commit('DELETE_ROW_IN_BUFFER', row)
        dispatch('correctMultiSelect')
        return
      }
      const position = computeRowInsertPosition(
        oldRow,
        allRows,
        view.sortings,
        fields,
        $registry,
        view.group_bys
      )
      if (position.isFirst) {
        commit('SET_BUFFER_START_INDEX', getters.getBufferStartIndex - 1)
      }
      commit('SET_COUNT', getters.getCount - 1)
      dispatch('correctMultiSelect')
    }

    const replaceAtPosition = (
      rowId,
      newRowValues,
      { sortedIndex, isFirst, isLast }
    ) => {
      if (getters.isGroupByMode) {
        const oldLocation = state.groupBy.rowLocations[rowId]

        if (oldLocation) {
          commit('REMOVE_ROW_AT_LOCATION', {
            sectionKey: oldLocation.sectionKey,
            position: oldLocation.position,
            rowId,
          })
        }
        // Resolve the insert location after removing the row so the section's positions
        // are already reindexed and the returned absolute position is correct.
        const { location: newLocation } = resolveGroupByInsertLocation(
          { getters, state, registry: $registry },
          { row: newRowValues, view, fields }
        )
        commit('INSERT_ROW_AT_LOCATION', {
          sectionKey: newLocation.sectionKey,
          position: newLocation.position,
          row: newRowValues,
        })
        dispatch('correctMultiSelect')
        return
      }

      const allRows = getters.getAllRows
      const index = allRows.findIndex((r) => r.id === rowId)
      const oldIsFirst = index === 0
      const oldIsLast = index === allRows.length - 1
      const oldRowInBuffer =
        (oldIsFirst && getters.getBufferStartIndex === 0) ||
        (oldIsLast && getters.getBufferEndIndex === getters.getCount) ||
        (index > 0 && index < allRows.length - 1)

      if (oldRowInBuffer) {
        commit('UPDATE_ROW_IN_BUFFER', { row, values, metadata })
        commit('SET_BUFFER_LIMIT', getters.getBufferLimit - 1)
      } else if (oldIsFirst || oldIsLast) {
        commit('DELETE_ROW_IN_BUFFER_WITHOUT_UPDATE', row)
        commit('SET_BUFFER_LIMIT', getters.getBufferLimit - 1)
      } else {
        const oldPosition = computeRowInsertPosition(
          oldRow,
          allRows.filter((r) => r.id !== oldRow.id),
          view.sortings,
          fields,
          $registry,
          view.group_bys
        )
        if (oldPosition.isFirst) {
          commit('SET_BUFFER_START_INDEX', getters.getBufferStartIndex - 1)
        }
      }

      const newIndex = sortedIndex
      const newIsFirst = isFirst
      const newIsLast = isLast
      const newRowInBuffer =
        (newIsFirst && getters.getBufferStartIndex === 0) ||
        (newIsLast && getters.getBufferEndIndex === getters.getCount - 1) ||
        (!newIsFirst && !newIsLast)

      if (oldRowInBuffer && newRowInBuffer) {
        if (index !== newIndex) {
          commit('MOVE_EXISTING_ROW_IN_BUFFER', {
            row: oldRow,
            index: newIndex,
          })
        }
        commit('SET_BUFFER_LIMIT', getters.getBufferLimit + 1)
      } else if (newRowInBuffer) {
        commit('INSERT_EXISTING_ROW_IN_BUFFER_AT_INDEX', {
          row: newRowValues,
          index: newIndex,
        })
        commit('SET_BUFFER_LIMIT', getters.getBufferLimit + 1)
      } else if (newIsFirst) {
        commit('SET_BUFFER_START_INDEX', getters.getBufferStartIndex + 1)
      }

      if (oldRowInBuffer && !newRowInBuffer && (newIsFirst || newIsLast)) {
        commit('DELETE_ROW_IN_BUFFER_WITHOUT_UPDATE', row)
      }
      dispatch('correctMultiSelect')
    }

    const applyMatchFlags = (rowId, { matchFilters, matchSortings }) => {
      const targetRow = getters.getAllRows.find((row) => row.id === rowId)
      if (!targetRow?._) {
        return
      }

      commit('SET_ROW_MATCH_FILTERS', { row: targetRow, value: matchFilters })
      commit('SET_ROW_MATCH_SORTINGS', {
        row: targetRow,
        value: matchSortings,
      })
    }

    const rowsForMatchCheck = () => getters.getAllRows

    handleRowUpdated({
      context: createRowLifecycleContext({
        registry: $registry,
        view,
        fields,
        groupBys: view.group_bys,
      }),
      mutations: {
        insertAtPosition,
        remove,
        replaceAtPosition,
        applyMatchFlags,
        rowsForMatchCheck,
      },
      oldRow,
      newRow,
    })

    clearPendingFieldOperations()
  },
  /**
   * Called when the user wants to delete an existing row in the table.
   */
  async deleteExistingRow(
    { commit, dispatch, getters },
    { table, view, row, fields, getScrollTop }
  ) {
    const { $registry, $client, $i18n, $config } = this
    commit('SET_ROW_LOADING', { row, value: true })

    try {
      await RowService($client).delete(table.id, row.id, getters.getLastGridId)
      await dispatch('deletedExistingRow', {
        view,
        fields,
        row,
        getScrollTop,
      })
      await dispatch('fetchByScrollTopDelayed', {
        scrollTop: getScrollTop(),
        fields,
      })
      dispatch('fetchAllFieldAggregationData', { view })
    } catch (error) {
      commit('SET_ROW_LOADING', { row, value: false })
      throw error
    }
  },
  /**
   * Attempt to delete all multi-selected rows.
   */
  async deleteSelectedRows(
    { dispatch, getters },
    { table, view, fields, getScrollTop }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const selectionType = getters.getSelectionType
    let rowsToDelete = []

    if (selectionType === GRID_VIEW_MULTI_SELECT_CHECKBOX) {
      rowsToDelete = getters.getCheckboxSelectedRows
    } else if (selectionType === GRID_VIEW_MULTI_SELECT_AREA) {
      if (getters.areMultiSelectRowsWithinBuffer) {
        rowsToDelete = getters.getSelectedRows
      } else {
        const [minRowIndex, maxRowIndex] = getters.getMultiSelectRowIndexSorted
        const limit = maxRowIndex - minRowIndex + 1
        rowsToDelete = await dispatch('fetchRowsByIndex', {
          startIndex: minRowIndex,
          limit,
          includeFields: fields,
        })
      }
    }

    if (rowsToDelete.length === 0) {
      return
    }

    const rowIdsToDelete = rowsToDelete.map((r) => r.id)
    await RowService($client).batchDelete(
      table.id,
      rowIdsToDelete,
      getters.getLastGridId
    )

    for (const row of rowsToDelete) {
      await dispatch('deletedExistingRow', {
        view,
        fields,
        row,
        getScrollTop,
      })
    }
    dispatch('clearAndDisableMultiSelect', { view })
    await dispatch('fetchByScrollTopDelayed', {
      scrollTop: getScrollTop(),
      fields,
    })
    dispatch('fetchAllFieldAggregationData', { view })
  },
  /**
   * Called after an existing row has been deleted, which could be by the user or
   * via another channel.
   */
  async deletedExistingRow(
    { commit, getters, dispatch },
    { view, fields, row }
  ) {
    const { $registry } = this
    row = clone(row)
    populateRow(row)

    // The lifecycle helper only evaluates filters/sortings, so the search match
    // is still gated here against the active search term.
    await dispatch('updateSearchMatchesForRow', { row, fields })
    if (!row._.matchSearch) {
      return
    }

    handleRowDeleted({
      context: createRowLifecycleContext({
        registry: $registry,
        view,
        fields,
        groupBys: view.group_bys,
      }),
      mutations: {
        remove: (rowId) => {
          if (getters.isGroupByMode) {
            const groupByFields = getGroupByFieldsFromActiveGroupBys(
              getters.getActiveGroupBys,
              fields
            )
            commit('UPDATE_GROUP_BY_TREE_PATH_COUNT', {
              path: groupPathFromRow(row, groupByFields, $registry),
              fields: groupByFields,
              delta: -1,
              registry: $registry,
            })
          }

          const allRows = getters.getAllRows
          const idx = allRows.findIndex((r) => r.id === rowId)
          if (idx >= 0) {
            commit('DELETE_ROW_IN_BUFFER', row)
            dispatch('correctMultiSelect')
            return
          }
          const position = computeRowInsertPosition(
            row,
            allRows,
            view.sortings,
            fields,
            $registry,
            view.group_bys
          )
          if (position.isFirst) {
            commit('SET_BUFFER_START_INDEX', getters.getBufferStartIndex - 1)
          }
          commit('SET_COUNT', getters.getCount - 1)
          dispatch('correctMultiSelect')
        },
        rowsForMatchCheck: () => getters.getAllRows,
      },
      row,
    })
  },
  /**
   * Triggered when a row has been changed, or has a pending change in the provided
   * overrides.
   */
  onRowChange(
    { dispatch, commit, getters, state },
    { view, row, fields, overrides = {} }
  ) {
    const lifecycleRow =
      Object.keys(overrides).length > 0
        ? Object.assign({}, row, overrides)
        : row
    const groupByFields = getters.isGroupByMode
      ? getGroupByFieldsFromActiveGroupBys(getters.getActiveGroupBys, fields)
      : []
    const expectedSectionKey =
      groupByFields.length > 0
        ? pathKey(
            groupPathFromRow(lifecycleRow, groupByFields, this.$registry),
            groupByFields
          )
        : null
    reapplyMatchFlags({
      context: createRowLifecycleContext({
        registry: this.$registry,
        view,
        fields,
        groupBys: view.group_bys,
      }),
      mutations: {
        applyMatchFlags: (rowId, { matchFilters, matchSortings }) => {
          // A row sitting outside its expected section no longer matches the sort.
          const location = state.groupBy.rowLocations[rowId]
          const rowOutsideExpectedSection =
            expectedSectionKey !== null &&
            location &&
            location.sectionKey !== expectedSectionKey
          commit('SET_ROW_MATCH_FILTERS', { row, value: matchFilters })
          commit('SET_ROW_MATCH_SORTINGS', {
            row,
            value: rowOutsideExpectedSection ? false : matchSortings,
          })
        },
        rowsForMatchCheck: () => getters.getAllRows,
      },
      row: lifecycleRow,
    })
    dispatch('updateSearchMatchesForRow', { row, fields, overrides })
  },
  /**
   * Changes the current search parameters if provided and optionally refreshes which
   * cells match the new search parameters by updating every rows row._.matchSearch and
   * row._.fieldSearchMatches attributes.
   */
  updateSearch(
    { commit, dispatch, getters, state },
    {
      fields,
      activeSearchTerm = state.activeSearchTerm,
      hideRowsNotMatchingSearch = state.hideRowsNotMatchingSearch,
      refreshMatchesOnClient = true,
    }
  ) {
    const { $registry, $client, $i18n, $config } = this
    commit('SET_SEARCH', { activeSearchTerm, hideRowsNotMatchingSearch })
    if (refreshMatchesOnClient) {
      getters.getAllRows.forEach((row) =>
        dispatch('updateSearchMatchesForRow', {
          row,
          fields,
          forced: true,
        })
      )
    }
  },
  /**
   * Updates a single row's row._.matchSearch and row._.fieldSearchMatches based on the
   * current search parameters and row data. Overrides can be provided which can be used
   * to override a row's field values when checking if they match the search parameters.
   */
  updateSearchMatchesForRow(
    { commit, getters, rootGetters },
    { row, fields = null, overrides, forced = false }
  ) {
    const { $registry, $config } = this
    // Avoid computing search on table loading
    if (getters.getActiveSearchTerm || forced) {
      const rowSearchMatches = calculateSingleRowSearchMatches(
        row,
        getters.getActiveSearchTerm,
        getters.isHidingRowsNotMatchingSearch,
        fields,
        $registry,
        getDefaultSearchModeFromEnv($config),
        overrides
      )

      commit('SET_ROW_SEARCH_MATCHES', rowSearchMatches)
    }
  },
  /**
   * Refreshes the row in the store if the given rowId exists. If the row
   * doesn't exist in the store, nothing will happen. This method ensures that
   * the row refreshed is the one of this store, because it could be that the
   * row object could come from another store.
   */
  async refreshRowById(
    { dispatch, getters },
    {
      grid,
      rowId,
      fields,
      getScrollTop = undefined,
      isRowOpenedInModal = undefined,
    }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const row = getters.getRow(rowId)
    if (row === undefined) {
      return
    }

    await dispatch('refreshRow', {
      grid,
      row,
      fields,
      getScrollTop,
      isRowOpenedInModal,
    })
  },
  /**
   * The row is going to be removed or repositioned if the matchFilters and
   * matchSortings state is false. It will make the state correct.
   */
  async refreshRow(
    { dispatch, commit, getters, state },
    {
      grid,
      row,
      fields,
      getScrollTop = undefined,
      isRowOpenedInModal = undefined,
    }
  ) {
    const { $registry, $client, $i18n, $config } = this
    if (getters.getRow(row.id) === undefined) {
      return
    }

    const rowShouldBeHidden = !row._.matchFilters || !row._.matchSearch
    const openedInModal =
      isRowOpenedInModal !== undefined ? isRowOpenedInModal(row) : false
    let handledLocally = false
    if (row._.selectedBy.length === 0 && rowShouldBeHidden && !openedInModal) {
      if (getters.isGroupByMode) {
        const groupByFields = getGroupByFieldsFromActiveGroupBys(
          getters.getActiveGroupBys,
          fields
        )
        commit('UPDATE_GROUP_BY_TREE_PATH_COUNT', {
          path: groupPathFromRow(row, groupByFields, $registry),
          fields: groupByFields,
          delta: -1,
          registry: $registry,
        })
      }
      commit('DELETE_ROW_IN_BUFFER', row)
    } else if (row._.selectedBy.length === 0 && !row._.matchSortings) {
      if (getters.isGroupByMode) {
        const groupByFields = getGroupByFieldsFromActiveGroupBys(
          getters.getActiveGroupBys,
          fields
        )
        const oldLocation = state.groupBy.rowLocations[row.id]
        const layout = getters.getGroupByLayout
        const oldSection = oldLocation
          ? findGroupByRowSection(layout, oldLocation.sectionKey, groupByFields)
          : null
        const newPath = groupPathFromRow(row, groupByFields, $registry)

        if (oldLocation) {
          commit('REMOVE_ROW_AT_LOCATION', {
            sectionKey: oldLocation.sectionKey,
            position: oldLocation.position,
            rowId: row.id,
          })
        }
        // Resolve the insert location after removing the row so the section's positions
        // are already reindexed and the returned absolute position is correct.
        const newLocation = getGroupByRowInsertLocation({
          row,
          view: grid,
          fields,
          registry: $registry,
          groupByFields,
          sectionRows: state.groupBy.sectionRows,
        })
        commit('INSERT_ROW_AT_LOCATION', {
          sectionKey: newLocation.sectionKey,
          position: newLocation.position,
          row,
        })

        if (
          oldSection &&
          pathKey(oldSection.path, groupByFields) !==
            pathKey(newPath, groupByFields)
        ) {
          commit('UPDATE_GROUP_BY_TREE_PATH_COUNT', {
            path: oldSection.path,
            fields: groupByFields,
            delta: -1,
            registry: $registry,
          })
          commit('UPDATE_GROUP_BY_TREE_PATH_COUNT', {
            path: newPath,
            fields: groupByFields,
            delta: 1,
            registry: $registry,
          })
        }
        commit('SET_ROW_MATCH_SORTINGS', { row, value: true })
        dispatch('correctMultiSelect')
        handledLocally = true
      } else {
        await dispatch('updatedExistingRow', {
          view: grid,
          fields,
          row,
          values: row,
        })
        commit('SET_ROW_MATCH_SORTINGS', { row, value: true })
      }
    }
    if (getScrollTop !== undefined && !handledLocally) {
      dispatch('fetchByScrollTopDelayed', {
        scrollTop: getScrollTop(),
        fields,
      })
    }
  },
  updateRowMetadata(
    { commit, getters, dispatch },
    { tableId, rowId, rowMetadataType, updateFunction }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const row = getters.getRow(rowId)
    if (row) {
      commit('UPDATE_ROW_METADATA', { row, rowMetadataType, updateFunction })
    }
  },
  /**
   * Clears the values of all multi-selected cells by updating them to their null values.
   */
  async clearValuesFromMultipleCellSelection(
    { getters, dispatch },
    { table, view, allVisibleFields, allFieldsInTable, getScrollTop }
  ) {
    const { $registry, $client, $i18n, $config } = this
    const [minFieldIndex, maxFieldIndex] =
      getters.getMultiSelectFieldIndexSorted

    const [minRowIndex, maxRowIndex] = getters.getMultiSelectRowIndexSorted
    const numberOfRowsSelected = maxRowIndex - minRowIndex + 1

    const selectedFields = allVisibleFields.slice(
      minFieldIndex,
      maxFieldIndex + 1
    )

    // Get the empty value for each selected field
    const emptyValues = selectedFields.map((field) =>
      $registry.get('field', field.type).getEmptyValue(field)
    )

    // Copy the empty value array once for each row selected
    const data = []
    for (let index = 0; index < numberOfRowsSelected; index++) {
      data.push(emptyValues)
    }

    await dispatch('updateDataIntoCells', {
      table,
      view,
      allVisibleFields,
      allFieldsInTable,
      getScrollTop,
      textData: data,
      rowIndex: minRowIndex,
      fieldIndex: minFieldIndex,
    })
  },
  /**
   * Add the fieldId to the list of pending field operations for the given rowIds.
   * This is used to show a loading spinner when a field is being updated. For example,
   * the AI field type uses this to show a spinner when the AI values are being
   * generated in a background task.
   */
  setPendingFieldOperations({ commit }, { fieldId, rowIds, value = true }) {
    commit('SET_PENDING_FIELD_OPERATIONS', { fieldId, rowIds, value })
  },
  AIValuesGenerationError({ commit, dispatch }, { fieldId, rowIds, error }) {
    const { $registry, $client, $i18n, $config } = this
    // If rowIds is empty, clear ALL pending operations for this field.
    if (rowIds.length === 0) {
      commit('CLEAR_ALL_PENDING_FIELD_OPERATIONS_FOR_FIELD', { fieldId })
    } else {
      commit('SET_PENDING_FIELD_OPERATIONS', { fieldId, rowIds, value: false })
    }
    dispatch(
      'toast/error',
      {
        title: $i18n.t('gridView.AIValuesGenerationErrorTitle'),
        message:
          (error && error.charAt(0).toUpperCase() + error.slice(1)) ||
          $i18n.t('gridView.AIValuesGenerationErrorMessage'),
      },
      { root: true }
    )
  },
  setRowHeight({ commit, dispatch, getters }, value) {
    commit('UPDATE_ROW_HEIGHT', value)
  },
  toggleCheckboxRowSelection({ commit, dispatch, state, getters }, { row }) {
    const { $registry, $client, $i18n, $config } = this
    const rowId = row.id
    const limit = $config.public.baserowRowPageSizeLimit
    const checked = state.checkboxSelectedRows.includes(rowId)

    if (!checked && state.checkboxSelectedRows.length >= limit) {
      return
    }

    if (!checked) {
      commit('ADD_CHECKBOX_SELECTED_ROW', rowId)
    } else if (state.checkboxSelectedRows.length === 1) {
      dispatch('clearCheckboxSelections')
      commit('SET_MULTISELECT_ACTIVE', false)
      commit('SET_SELECTION_TYPE', null)
    } else {
      commit('REMOVE_CHECKBOX_SELECTED_ROW', rowId)
    }
    if (
      state.checkboxSelectedRows.length > 0 &&
      getters.getSelectionType !== GRID_VIEW_MULTI_SELECT_CHECKBOX
    ) {
      dispatch('setSelectionType', {
        selectionType: GRID_VIEW_MULTI_SELECT_CHECKBOX,
      })
    }
  },
  setSelectionType({ commit, dispatch, getters }, { selectionType }) {
    const { $registry, $client, $i18n, $config } = this
    commit('SET_SELECTION_TYPE', selectionType)

    if (selectionType === GRID_VIEW_MULTI_SELECT_CHECKBOX) {
      commit('SET_MULTISELECT_ACTIVE', true)
      commit('CLEAR_AREA_SELECTION')
      commit('CLEAR_AREA_START_SELECTION')
    } else if (selectionType === GRID_VIEW_MULTI_SELECT_AREA) {
      commit('SET_MULTISELECT_ACTIVE', true)
      dispatch('clearCheckboxSelections', { commit, state })
    } else {
      commit('CLEAR_AREA_SELECTION')
      dispatch('clearCheckboxSelections', { commit, state })
      commit('SET_MULTISELECT_ACTIVE', false)
    }
  },
  clearCheckboxSelectedRows({ commit }) {
    commit('CLEAR_CHECKBOX_SELECTED_ROWS')
  },
}

export const getters = {
  isLoaded(state) {
    return state.loaded
  },
  getLastGridId(state) {
    return state.lastGridId
  },
  getCount(state) {
    return state.count
  },
  canExcludeCount(state) {
    // If the count has already been set for the view, there's no need to fetch it again
    // considering it's slow for large tables. Every time something changes in the view,
    // the refresh action is called making sure the count is up to date.
    return state.count > 0
  },
  getRowHeight(state) {
    return state.rowHeight
  },
  getRowsTop(state) {
    return state.rowsTop
  },
  getRowsLength(state) {
    if (state.activeGroupBys.length > 0) {
      return getGroupByLayoutFromState(state).totalRowCount
    }
    return state.rows.length
  },
  getPlaceholderHeight(state) {
    return state.count * state.rowHeight
  },
  getRowPadding(state) {
    return state.rowPadding
  },
  getAllRows(state) {
    if (state.activeGroupBys.length > 0) {
      return getGroupByRowsInLayoutOrder(state)
    }
    return state.rows
  },
  getRow: (state) => (id) => {
    if (state.activeGroupBys.length > 0) {
      // rowLocations is the authoritative index: a loaded grouped row always has
      // an entry, so a miss means the row simply isn't in the buffer.
      const location = state.groupBy.rowLocations[id]
      if (!location) {
        return undefined
      }
      return state.groupBy.sectionRows[location.sectionKey]?.[location.position]
    }
    return state.rows.find((row) => row.id === id)
  },
  getRows(state) {
    return state.rows.slice(state.rowsStartIndex, state.rowsEndIndex)
  },
  getRowsStartIndex(state) {
    return state.rowsStartIndex
  },
  getRowsEndIndex(state) {
    return state.rowsEndIndex
  },
  getBufferRequestSize(state) {
    return state.bufferRequestSize
  },
  getBufferStartIndex(state) {
    return state.bufferStartIndex
  },
  getBufferEndIndex(state) {
    return state.bufferStartIndex + state.bufferLimit
  },
  getBufferLimit(state) {
    return state.bufferLimit
  },
  getScrollTop(state) {
    return state.scrollTop
  },
  getWindowHeight(state) {
    return state.windowHeight
  },
  getAllFieldOptions(state) {
    return state.fieldOptions
  },
  getOrderedFieldOptions: (state, getters) => (fields) => {
    const primaryField = fields.find((f) => f.primary === true)
    const primaryFieldId = primaryField?.id || -1

    return Object.entries(getters.getAllFieldOptions)
      .map(([fieldIdStr, options]) => [parseInt(fieldIdStr), options])
      .sort(([a, { order: orderA }], [b, { order: orderB }]) => {
        const isAPrimary = a === primaryFieldId
        const isBPrimary = b === primaryFieldId

        // Place primary field first
        if (isAPrimary === true && !isBPrimary) {
          return -1
        } else if (isBPrimary === true && !isAPrimary) {
          return 1
        }

        // Then by order
        if (orderA > orderB) {
          return 1
        } else if (orderA < orderB) {
          return -1
        }

        // Finally by id if order is the same
        return a - b
      })
  },
  getOrderedVisibleFieldOptions: (state, getters) => (fields) => {
    return getters
      .getOrderedFieldOptions(fields)
      .filter(([fieldId, options]) => options.hidden === false)
  },
  getNumberOfVisibleFields(state) {
    return Object.values(state.fieldOptions).filter((fo) => fo.hidden === false)
      .length
  },
  isFirst: (state) => (id) => {
    const index = state.rows.findIndex((row) => row.id === id)
    return index === 0
  },
  isLast: (state) => (id) => {
    const index = state.rows.findIndex((row) => row.id === id)
    return index === state.rows.length - 1
  },
  getAddRowHover(state) {
    return state.addRowHover
  },
  getActiveSearchTerm(state) {
    return state.activeSearchTerm
  },
  isHidingRowsNotMatchingSearch(state) {
    return state.hideRowsNotMatchingSearch
  },
  getServerSearchTerm(state) {
    return state.hideRowsNotMatchingSearch ? state.activeSearchTerm : false
  },
  getHighestOrder(state) {
    let order = new BigNumber('0.00000000000000000000')
    const visitRow = (r) => {
      const rOrder = new BigNumber(r.order)
      if (rOrder.isGreaterThan(order)) {
        order = rOrder
      }
    }
    if (state.activeGroupBys.length > 0) {
      forEachGroupByRow(state.groupBy.sectionRows, visitRow)
    } else {
      state.rows.forEach(visitRow)
    }
    return order
  },
  isMultiSelectActive(state) {
    return state.multiSelectActive
  },
  isMultiSelectHolding(state) {
    return state.multiSelectHolding
  },
  getMultiSelectRowIndexSorted(state) {
    return [
      Math.min(state.multiSelectHeadRowIndex, state.multiSelectTailRowIndex),
      Math.max(state.multiSelectHeadRowIndex, state.multiSelectTailRowIndex),
    ]
  },
  getMultiSelectFieldIndexSorted(state) {
    return [
      Math.min(
        state.multiSelectHeadFieldIndex,
        state.multiSelectTailFieldIndex
      ),
      Math.max(
        state.multiSelectHeadFieldIndex,
        state.multiSelectTailFieldIndex
      ),
    ]
  },
  getMultiSelectHeadFieldIndex(state) {
    return state.multiSelectHeadFieldIndex
  },
  getMultiSelectTailFieldIndex(state) {
    return state.multiSelectTailFieldIndex
  },
  getMultiSelectHeadRowIndex(state) {
    return state.multiSelectHeadRowIndex
  },
  getMultiSelectTailRowIndex(state) {
    return state.multiSelectTailRowIndex
  },
  getMultiSelectStartRowIndex(state) {
    return state.multiSelectStartRowIndex
  },
  getMultiSelectStartFieldIndex(state) {
    return state.multiSelectStartFieldIndex
  },
  // Get the index of a row given it's row id.
  // This will calculate the row index from the current buffer position and offset.
  getRowIndexById: (state, getters) => (rowId) => {
    if (getters.isGroupByMode) {
      return getGroupByVisibleIndexForLocation(
        state,
        state.groupBy.rowLocations[rowId]
      )
    }
    const bufferIndex = state.rows.findIndex((r) => r.id === rowId)
    if (bufferIndex !== -1) {
      return getters.getBufferStartIndex + bufferIndex
    }
    return -1
  },
  getRowIdByIndex: (state, getters) => (rowIndex) => {
    if (getters.isGroupByMode) {
      return getGroupByRowIdByVisibleIndex(state, rowIndex)
    }
    const row = state.rows[rowIndex - getters.getBufferStartIndex]
    if (row) {
      return row.id
    }
    return -1
  },
  getFieldIdByIndex: (state, getters) => (fieldIndex, fields) => {
    const orderedFieldOptions = getters.getOrderedVisibleFieldOptions(fields)
    if (orderedFieldOptions[fieldIndex]) {
      return orderedFieldOptions[fieldIndex][0]
    }
    return -1
  },
  // Check if all the multi-select rows are within the row buffer
  areMultiSelectRowsWithinBuffer(state, getters) {
    const [minRow, maxRow] = getters.getMultiSelectRowIndexSorted

    if (getters.isGroupByMode) {
      for (let index = minRow; index <= maxRow; index++) {
        if (getters.getRowIdByIndex(index) === -1) {
          return false
        }
      }
      return true
    }

    return (
      minRow >= getters.getBufferStartIndex &&
      maxRow <= getters.getBufferEndIndex
    )
  },
  // Return all rows within a multi-select grid if they are within the current row buffer
  getSelectedRows(state, getters) {
    const selectionType = getters.getSelectionType

    if (selectionType === GRID_VIEW_MULTI_SELECT_CHECKBOX) {
      return getters.getAllRows.filter((row) =>
        state.checkboxSelectedRows.includes(row.id)
      )
    }

    const [minRow, maxRow] = getters.getMultiSelectRowIndexSorted
    if (getters.isGroupByMode) {
      if (!getters.areMultiSelectRowsWithinBuffer) {
        return []
      }
      const rows = []
      for (let index = minRow; index <= maxRow; index++) {
        const rowId = getters.getRowIdByIndex(index)
        const row = getters.getRow(rowId)
        if (row) {
          rows.push(row)
        }
      }
      return rows
    }
    if (getters.areMultiSelectRowsWithinBuffer) {
      return state.rows.slice(
        minRow - state.bufferStartIndex,
        maxRow - state.bufferStartIndex + 1
      )
    }
    return []
  },
  getSelectedFields: (state, getters) => (fields) => {
    const [minField, maxField] = getters.getMultiSelectFieldIndexSorted
    const selectedFields = []

    const fieldMap = fields.reduce((acc, field) => {
      acc[field.id] = field
      return acc
    }, {})

    for (let i = minField; i <= maxField; i++) {
      const fieldId = getters.getFieldIdByIndex(i, fields)
      if (fieldId !== -1) {
        selectedFields.push(fieldMap[fieldId])
      }
    }
    return selectedFields
  },
  getAllFieldAggregationData(state) {
    return state.fieldAggregationData
  },
  getActiveGroupBys(state) {
    return state.activeGroupBys
  },
  isGroupByMode(state) {
    return state.activeGroupBys.length > 0
  },
  getGroupByCollapse(state) {
    return state.groupBy.collapse
  },
  // No-arg cached getter: derives the group-by fields from state so the (expensive)
  // layout build runs once per relevant state change instead of on every call with a
  // freshly-mapped fields array. Shared by getAllRows, the actions, and the component.
  getGroupByLayout(state) {
    return getGroupByLayoutFromState(state)
  },
  getGroupBySectionRowsMap: (state) => {
    return makeSectionRowsMap(state.groupBy.sectionRows)
  },
  getGroupByVisibleItems: (state, getters) => (groupByFields) => {
    return renderViewport({
      layout: getters.getGroupByLayout,
      sectionRows: getters.getGroupBySectionRowsMap,
      viewport: {
        scrollTop: state.scrollTop,
        clientHeight: state.windowHeight || 1000,
      },
      fields: groupByFields,
      rowHeight: state.rowHeight,
    })
  },
  hasSelectedCell(state, getters) {
    return getters.getAllRows.some((row) => {
      return row._.selected && row._.selectedFieldId !== -1
    })
  },
  getAdhocFiltering(state) {
    return state.adhocFiltering
  },
  getAdhocSorting(state) {
    return state.adhocSorting
  },
  hasPendingFieldOps: (state) => (fieldId, rowId) => {
    const key = getPendingOperationKey(fieldId, rowId)
    return state.pendingFieldOps[key] !== undefined
  },
  getCheckboxSelectedRows: (state, getters) => {
    return getters.getAllRows.filter((row) =>
      state.checkboxSelectedRows.includes(row.id)
    )
  },
  getCheckboxSelectedRowsIds: (state) => {
    return state.checkboxSelectedRows
  },
  getSelectionType(state) {
    return state.selectionType
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
