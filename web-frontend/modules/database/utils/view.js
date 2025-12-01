import { firstBy } from 'thenby'
import BigNumber from 'bignumber.js'
import { maxPossibleOrderValue } from '@baserow/modules/database/viewTypes'
import { escapeRegExp, isSecureURL } from '@baserow/modules/core/utils/string'
import { SearchMode } from '@baserow/modules/database/utils/search'
import { convertStringToMatchBackendTsvectorData } from '@baserow/modules/database/search/regexes'
import { DEFAULT_SORT_TYPE_KEY } from '@baserow/modules/database/constants'

export const DEFAULT_VIEW_ID_COOKIE_NAME = 'defaultViewId'

/**
 * Generates a sort function based on the provided sortings.
 */
export function getRowSortFunction($registry, sortings, fields, groupBys = []) {
  let sortFunction = firstBy()
  const combined = [...groupBys, ...sortings]
  combined.forEach((sort) => {
    // Find the field that is related to the sort.
    const field = fields.find((f) => f.id === sort.field)

    if (field !== undefined) {
      const fieldName = `field_${field.id}`
      const fieldType = $registry.get('field', field.type)
      const sortTypes = fieldType.getSortTypes(field)
      const fieldSortFunction = sortTypes[sort.type].function(
        fieldName,
        sort.order,
        field
      )
      sortFunction = sortFunction.thenBy(fieldSortFunction)
    }
  })

  sortFunction = sortFunction.thenBy((a, b) =>
    new BigNumber(a.order).minus(new BigNumber(b.order)).toNumber()
  )
  sortFunction = sortFunction.thenBy((a, b) => a.id - b.id)
  return sortFunction
}

/**
 * Generates a sort function for fields based on order and id.
 */
export function sortFieldsByOrderAndIdFunction(
  fieldOptions,
  primaryAlwaysFirst = false
) {
  return (a, b) => {
    if (primaryAlwaysFirst) {
      // If primary must always be first, then first by primary.
      if (a.primary > b.primary) {
        return -1
      } else if (a.primary < b.primary) {
        return 1
      }
    }

    const orderA = fieldOptions[a.id]
      ? fieldOptions[a.id].order
      : maxPossibleOrderValue
    const orderB = fieldOptions[b.id]
      ? fieldOptions[b.id].order
      : maxPossibleOrderValue

    // First by order.
    if (orderA > orderB) {
      return 1
    } else if (orderA < orderB) {
      return -1
    }

    // Then by id.
    return a.id - b.id
  }
}

/**
 * Returns only fields that are visible (not hidden).
 */
export function filterVisibleFieldsFunction(fieldOptions) {
  return (field) => {
    const exists = Object.prototype.hasOwnProperty.call(fieldOptions, field.id)
    return !exists || !fieldOptions[field.id].hidden
  }
}

/**
 * Returns only fields that are visible (not hidden).
 */
export function filterHiddenFieldsFunction(fieldOptions) {
  return (field) => {
    const exists = Object.prototype.hasOwnProperty.call(fieldOptions, field.id)
    return exists && fieldOptions[field.id].hidden
  }
}

/**
 * Represents a node in a tree structure used for grouped filters.
 * A group node is made of a filterType (AND or OR), a list of filters and a parent.
 * If the parent is null it means that it is the root node. If the parent is not
 * null it means that it is a child of the parent node, and the constructor will take care to
 * add itself to the children of the parent node, so that we can later traverse the tree
 * from the root node and check if a row matches the filters.
 */
export const TreeGroupNode = class {
  /**
   * Constructs a new TreeGroupNode.
   *
   * @param {string} filterType - The type of filter (e.g., 'AND' or 'OR').
   * @param {TreeGroupNode} [parent=null] - The parent node of this node. Null for the root node.
   * @param {number} [groupId=null] - The ID of the group this node represents. Null for the root node.
   */
  constructor(filterType, parent = null, groupId = null) {
    this.filterType = filterType
    this.groupId = groupId
    this.parent = parent
    this.filters = []
    this.children = []
    if (parent) {
      parent.children.push(this)
    }
  }

  /**
   * Finds the group node with the provided ID in the tree rooted at this node.
   *
   * @param {number} groupId - The ID of the group to find.
   * @returns {TreeGroupNode|null} - The group node with the provided ID or null if it is not found.
   */
  findNodeByGroupId(groupId) {
    if (this.groupId === groupId) {
      return this
    }
    for (const groupNode of this.children) {
      const found = groupNode.findNodeByGroupId(groupId)
      if (found) {
        return found
      }
    }
    return null
  }

  /**
   * Checks if this node or any of its descendants has filters.
   *
   * @returns {boolean} - True if there are filters, false otherwise.
   */
  hasFilters() {
    return this.filters.length > 0 || this.children.some((c) => c.hasFilters())
  }

  /**
   * Adds a filter object to this node list of filters.
   *
   * @param {object} filter - The filter to add.
   */
  addFilter(filter) {
    this.filters.push(filter)
  }

  /**
   * Serializes the filter tree rooted at this node. The serialized version will be in the form:
   * {
   *  filter_type: 'AND' | 'OR',
   *  filters: [
   *    {
   *       type: 'contains' | 'does_not_contain' | 'is' | 'is_not' | 'is_empty' | 'is_not_empty' | etc.,
   *       field: 1,
   *       value: 'some value'
   *     },
   *     ...
   *   ],
   *   groups: [
   *     {
   *        filter_type: 'AND' | 'OR',
   *        filters: [
   *          type: 'contains' | 'does_not_contain' | 'is' | 'is_not' | 'is_empty' | 'is_not_empty' | etc.,
   *          field: 2,
   *          value: 'some other value'
   *        },
   *        ...
   *        ],
   *       groups: [...]
   *     },
   *    ...,
   *   ],
   * }
   *
   * @returns {object} - The serialized tree.
   */
  getFiltersTreeSerialized() {
    const serialized = {
      filter_type: this.filterType,
      filters: [],
      groups: [],
    }

    for (const filter of this.filters) {
      serialized.filters.push({
        type: filter.type,
        field: filter.field,
        value: filter.value,
      })
    }

    for (const groupNode of this.children) {
      serialized.groups.push(groupNode.getFiltersTreeSerialized())
    }
    return serialized
  }

  /**
   * Determines if a given row matches the conditions of this node and its descendants.
   * This function will recursively check if the row matches the filters of this node
   * and its descendants. If the filter type of this node is 'AND' then it will return
   * true if the row matches all the filters. If the filter type of this node is 'OR'
   * then it will return true if the row matches at least one of the filters.
   *
   * @param {object} $registry - The registry containing field and filter type information.
   * @param {Array} fields - The list of fields.
   * @param {object} rowValues - The values of the row being checked.
   * @returns {boolean} - True if the row matches, false otherwise.
   */
  matches($registry, fields, rowValues) {
    this.hasValidFilter = false

    for (const child of this.children) {
      const matches = child.matches($registry, fields, rowValues)

      if (child.hasValidFilter) {
        this.hasValidFilter = true
      }

      if (this.filterType === 'AND' && !matches) {
        return false
      } else if (this.filterType === 'OR' && matches) {
        return true
      }
    }
    const filterType = this.filterType

    for (const filter of this.filters) {
      const filterValue = String(filter.value ?? '')
      const field = fields.find((f) => f.id === filter.field)
      const fieldType = $registry.get('field', field.type)
      const viewFilterType = $registry.get('viewFilter', filter.type)
      const rowValue = rowValues[`field_${field.id}`]
      const matches = viewFilterType.matches(
        rowValue,
        filterValue,
        field,
        fieldType
      )

      if (matches === null) {
        continue
      }

      this.hasValidFilter = true

      if (filterType === 'AND' && !matches) {
        // With an `AND` filter type, the row must match all the filters, so if
        // one of the filters doesn't match we can mark it as invalid.
        return false
      } else if (filterType === 'OR' && matches) {
        // With an 'OR' filter type, the row only has to match one of the filters,
        // that is the case here so we can mark it as valid.
        return true
      }
    }
    if (filterType === 'AND') {
      // At this point with an `AND` condition the filter type matched all the
      // filters and therefore we can mark it as valid.
      return true
    } else if (filterType === 'OR') {
      // If no valid filters were found, return true (no filtering should be applied).
      // If there were valid filters but none matched, return false.
      return !this.hasValidFilter
    }
  }
}

/**
 * Creates a tree structure from given filters and filter groups. Groups are
 * first sorted by ID because parent groups have smaller IDs since they were
 * created before their children. In this way, we ensure that when a child node
 * is added to the tree, its parent will already be present.
 * Once the tree has been created, it adds all the filters to the respective
 * groups.
 *
 * @param {string} filterType - The root filter type.
 * @param {Array} filters - The list of filters.
 * @param {Array} filterGroups - The list of filter groups.
 * @returns {TreeGroupNode} - The root of the filter tree.
 */
export const createFiltersTree = (filterType, filters, filterGroups) => {
  const rootGroup = new TreeGroupNode(filterType)
  const filterGroupsById = { '': rootGroup }
  const filterGroupsOrderedById = filterGroups
    ? [...filterGroups].sort((a, b) => a.id - b.id)
    : []

  for (const filterGroup of filterGroupsOrderedById) {
    const parent = filterGroupsById[filterGroup.parent_group || '']
    filterGroupsById[filterGroup.id] = new TreeGroupNode(
      filterGroup.filter_type,
      parent,
      filterGroup.id
    )
  }

  for (const filter of filters) {
    const filterGroupId = filter.group || ''
    const filterGroup = filterGroupsById[filterGroupId]
    filterGroup.addFilter(filter)
  }
  return rootGroup
}

/**
 * A helper function that checks if the provided row values match the provided view
 * filters. Returning false indicates that the row should not be visible for that
 * view.
 */
export const matchSearchFilters = (
  $registry,
  filterType,
  filters,
  filterGroups,
  fields,
  values
) => {
  // If there aren't any filters then it is not possible to check if the row
  // matches any of the filters, so we can mark it as valid.
  if (filters.length === 0) {
    return true
  }

  const filterTree = createFiltersTree(filterType, filters, filterGroups)
  return filterTree.matches($registry, fields, values)
}

function _fullTextSearch(registry, field, value, activeSearchTerm) {
  const searchableString = registry
    .get('field', field.type)
    .toSearchableString(field, value)
  const fixedValue = convertStringToMatchBackendTsvectorData(searchableString)
  const fixedTerm = convertStringToMatchBackendTsvectorData(activeSearchTerm)
  if (fixedTerm.length === 0) {
    return false
  } else {
    const regexMatchingWordsThatStartWithTerm =
      '(^|\\s+)' + escapeRegExp(fixedTerm)
    return !!fixedValue.match(
      new RegExp(regexMatchingWordsThatStartWithTerm, 'gu')
    )
  }
}

function _compatSearchMode(registry, field, value, activeSearchTerm) {
  return registry
    .get('field', field.type)
    .containsFilter(value, activeSearchTerm, field)
}

export function valueMatchesActiveSearchTerm(
  searchMode,
  registry,
  field,
  value,
  activeSearchTerm
) {
  if (searchMode === SearchMode.FT_WITH_COUNT) {
    return _fullTextSearch(registry, field, value, activeSearchTerm)
  } else {
    return _compatSearchMode(registry, field, value, activeSearchTerm)
  }
}

function _findFieldsInRowMatchingSearch(
  row,
  activeSearchTerm,
  fields,
  registry,
  overrides,
  searchMode
) {
  const fieldSearchMatches = new Set()
  // If the row is loading then a temporary UUID is put in its id. We don't want to
  // accidentally match against that UUID as it will be shortly replaced with its
  // real id.
  if (
    !row._.loading &&
    row.id?.toString() === (activeSearchTerm || '').trim()
  ) {
    fieldSearchMatches.add('row_id')
  }
  for (const field of fields) {
    const fieldName = `field_${field.id}`
    const rowValue =
      fieldName in overrides ? overrides[fieldName] : row[fieldName]
    if (rowValue !== undefined && rowValue !== null) {
      const doesMatch = valueMatchesActiveSearchTerm(
        searchMode,
        registry,
        field,
        rowValue,
        activeSearchTerm
      )
      if (doesMatch) {
        fieldSearchMatches.add(field.id.toString())
      }
    }
  }

  return fieldSearchMatches
}

/**
 * Helper function which calculates if a given row and which of it's fields matches a
 * given search term. The rows values can be overridden by providing an overrides
 * object containing a mapping of the field name to override to a value that will be
 * used to check for matches instead of the rows real one. The rows values will not be
 * changed.
 */
export function calculateSingleRowSearchMatches(
  row,
  activeSearchTerm,
  hideRowsNotMatchingSearch,
  fields,
  registry,
  searchMode,
  overrides = {}
) {
  const searchIsBlank = activeSearchTerm === ''
  const fieldSearchMatches = searchIsBlank
    ? new Set()
    : _findFieldsInRowMatchingSearch(
        row,
        activeSearchTerm,
        fields,
        registry,
        overrides,
        searchMode
      )

  const matchSearch =
    !hideRowsNotMatchingSearch || searchIsBlank || fieldSearchMatches.size > 0
  return { row, matchSearch, fieldSearchMatches }
}

/**
 * Returns true is the empty value of the provided field matches the active search term.
 */
export function newFieldMatchesActiveSearchTerm(
  searchMode,
  registry,
  newField,
  activeSearchTerm
) {
  if (newField && activeSearchTerm !== '') {
    const fieldType = registry.get('field', newField.type)
    const defaultValue = fieldType.getDefaultValue(newField)

    return valueMatchesActiveSearchTerm(
      searchMode,
      registry,
      newField,
      defaultValue,
      activeSearchTerm
    )
  }
  return false
}

export function getGroupBy(rootGetters, viewId) {
  if (rootGetters['page/view/public/getIsPublic']) {
    const view = rootGetters['view/get'](viewId)
    return view.group_bys
      .map((groupBy) => {
        let serialized = `${groupBy.order === 'DESC' ? '-' : ''}field_${
          groupBy.field
        }`
        if (groupBy.type !== DEFAULT_SORT_TYPE_KEY) {
          serialized += `[${groupBy.type}]`
        }
        return serialized
      })
      .join(',')
  } else {
    return ''
  }
}

export function isAdhocSorting(app, workspace, view, publicView) {
  return (
    publicView ||
    (app.$hasPermission('database.table.view.list_sort', view, workspace.id) &&
      !app.$hasPermission(
        'database.table.view.create_sort',
        view,
        workspace.id
      ))
  )
}

/**
 * If filters, sorts or group bys are read only (i.e. formula fields) or there are
 * read-only fields and there's an activeSearchTerm, then the rows cannot be
 * optimistically because the backend calculates the read-only values based on other
 * fields and the UI cannot predict the outcome reliably.
 */
export function canRowsBeOptimisticallyUpdatedInView(
  $registry,
  view,
  fields,
  activeSearchTerm
) {
  const readOnlyFieldIds = new Set(
    fields
      .filter((f) => $registry.get('field', f.type).isReadOnlyField(f))
      .map((field) => String(field.id))
  )
  const hasReadOnlyField = (sort) => readOnlyFieldIds.has(String(sort.field))
  const readOnlyGroupBys = view.group_bys
    ? view.group_bys.some(hasReadOnlyField)
    : false
  const readOnlySorts = view.sortings.some(hasReadOnlyField)
  const readOnlyFilters = view.filters.some((filter) =>
    readOnlyFieldIds.has(String(filter.field))
  )

  // if any of the above conditions are true, then we cannot optimistically update rows
  // in this view
  const needsServerSideCalculation =
    readOnlyGroupBys ||
    readOnlySorts ||
    readOnlyFilters ||
    (activeSearchTerm && readOnlyFieldIds.size > 0)
  return !needsServerSideCalculation
}

export function getOrderBy(view, adhocSorting) {
  if (adhocSorting) {
    const serializeSort = (sort) => {
      let serialized = `${sort.order === 'DESC' ? '-' : ''}field_${sort.field}`
      if (sort.type !== DEFAULT_SORT_TYPE_KEY) {
        serialized += `[${sort.type}]`
      }
      return serialized
    }
    // Group bys first, then sorts to ensure that the order is correct.
    const groupBys = view.group_bys ? view.group_bys.map(serializeSort) : []
    const sorts = view.sortings.map(serializeSort)

    return [...groupBys, ...sorts].join(',')
  } else {
    return null
  }
}

export function isAdhocFiltering(app, workspace, view, publicView) {
  return (
    publicView ||
    (app.$hasPermission(
      'database.table.view.list_filter',
      view,
      workspace.id
    ) &&
      !app.$hasPermission(
        'database.table.view.create_filter',
        view,
        workspace.id
      ))
  )
}

export function getFilters(view, adhocFiltering) {
  const payload = {}
  if (adhocFiltering && !view.filters_disabled) {
    const {
      filter_type: filterType,
      filter_groups: filterGroups,
      filters,
    } = view
    const filterTree = createFiltersTree(filterType, filters, filterGroups)
    const serializedTree = filterTree.getFiltersTreeSerialized()
    payload.filters = [JSON.stringify(serializedTree)]
  }
  return payload
}

/**
 * Calculates the size of a UTF-8 encoded string in bytes - computes the size
 * of a string in UTF-8 encoding and utilizes the TextEncoder API if available.
 *
 * Using TextEncoder is preferred in Modern Browsers and Node.js Supported
 * environments because it provides a more efficient and accurate way to encode
 * strings into UTF-8 bytes and directly calculate the byte size of the encoded
 * string.
 *
 * In some older web browsers or environments where TextEncoder may not be available
 * (such as SSR where certain browser APIs are absent), it falls back to a less
 * accurate method and simply returns the length of the string.
 */
export function utf8ByteSize(str) {
  // Use TextEncoder if available (modern browsers and Node.js)
  if (typeof TextEncoder !== 'undefined') {
    const encoder = new TextEncoder()
    const data = encoder.encode(str)
    return data.length
  } else {
    // Fallback for older browsers (may not be as accurate)
    return str.length
  }
}

/**
 * Return the view that has been visited most recently or the first
 * available one that is capable of displaying the provided row data if required.
 * If no view is available that can display the row data, return undefined.
 */
export function getDefaultView(app, store, workspaceId, showRowModal) {
  // Put the most recently visited one first in the list.
  const defaultView = store.getters['view/default']
  const allViews = store.getters['view/getAllOrdered']
  const views = defaultView ? [defaultView, ...allViews] : allViews

  return views.find((view) => {
    const viewType = app.$registry.get('view', view.type)
    if (viewType.isDeactivated(workspaceId)) {
      return false
    }
    // Ensure that the view can display the row data if required.
    return showRowModal ? viewType.canShowRowModal() : true
  })
}

/*
 * Extracts the metadata from the provided data to populate the row.
 */
export function extractRowMetadata(data, rowId) {
  const metadata = data.row_metadata || {}
  return metadata[rowId] || {}
}

/**
 * Limit the size of a cookie's value by removing elements from an array
 * until it fits within the maximum allowed cookie size. The array is
 * assumed to be ordered by least important to most important, so the first
 * elements are removed first.
 *
 * @param {Array} arrayOfValues - The array of values to encode.
 * @param {Function} encodingFunc - The function to use to encode the array.
 * @param {Number} maxLength - The maximum allowed length of the encoded value string.
 * @returns {String} - The serialized value to save in the cookie with the
 * max number of elements that fit in, or an empty string if none fit.
 */
export function fitInCookieEncoded(
  arrayOfValues,
  encodingFunc,
  maxLength = 2048
) {
  for (let i = 0, l = arrayOfValues.length; i < l; i++) {
    const encoded = encodingFunc(arrayOfValues.slice(i))
    // The encoded URI will be serialized when saved in the cookie, so we
    // need to encode it first to get the correct byte size.
    const serialized = encodeURIComponent(encoded)
    if (utf8ByteSize(serialized) < maxLength) {
      return encoded
    }
  }
  return ''
}

export function decodeDefaultViewIdPerTable(value) {
  // backward compatibility, we used to store the array of default views
  // with a slightly different format
  if (Array.isArray(value)) {
    return value.map((item) => ({
      tableId: item.table_id,
      viewId: item.id,
    }))
  }

  const data = []
  for (const item of value.split(',')) {
    const [tableId, viewId] = item.split(':')
    if (tableId !== undefined && viewId !== undefined) {
      data.push({ tableId: parseInt(tableId), viewId: parseInt(viewId) })
    }
  }
  return data
}

export function encodeDefaultViewIdPerTable(data) {
  return data.map(({ tableId, viewId }) => `${tableId}:${viewId}`).join(',')
}

/**
 * Reads the default view for table from cookies.
 *
 * @param {Object} cookies - The cookies object.
 * @param {Number} tableId - The id of the table.
 * @param {String} cookieName - The name of the cookie.
 * @returns {Number|null} - The id of the default view for the table, or null if there
 * is no default view for the table.
 */
export function readDefaultViewIdFromCookie(
  cookies,
  tableId,
  cookieName = DEFAULT_VIEW_ID_COOKIE_NAME
) {
  try {
    const cookieValue = cookies.get(cookieName) || ''
    const defaultViews = decodeDefaultViewIdPerTable(cookieValue)
    const defaultView = defaultViews.find((view) => view.tableId === tableId)
    return defaultView ? defaultView.viewId : null
  } catch (error) {
    return null
  }
}

/**
 * Updates the default view for table in cookies (if it exists) or creates a new one if
 * it doesn't. The entry will be placed at the end of the list as the most recently
 * visited view. If the entire list does not fit in the cookie, the oldest entries (the
 * first ones) will be removed.
 *
 * @param {Object} cookies - The cookies object.
 * @param {Object} view - The view object.
 * @param {Object} config - The config object.
 * @param {String} cookieName - The name of the cookie.
 */
export function saveDefaultViewIdInCookie(
  cookies,
  view,
  config,
  cookieName = DEFAULT_VIEW_ID_COOKIE_NAME
) {
  const cookieValue = cookies.get(cookieName) || ''
  let defaultViews = decodeDefaultViewIdPerTable(cookieValue)

  function createEntry(view) {
    return { tableId: view.table_id, viewId: view.id }
  }

  try {
    const index = defaultViews.findIndex((obj) => obj.tableId === view.table_id)

    if (index !== -1) {
      const existingView = defaultViews.splice(index, 1)[0]
      existingView.viewId = view.id
      defaultViews.push(existingView)
    } else if (view.id !== view.slug) {
      defaultViews.push(createEntry(view))
    }
  } catch (error) {
    defaultViews = [createEntry(view)]
  } finally {
    const fittedListEncoded = fitInCookieEncoded(
      defaultViews,
      encodeDefaultViewIdPerTable
    )
    const secure = isSecureURL(config.PUBLIC_WEB_FRONTEND_URL)
    cookies.set(cookieName, fittedListEncoded, {
      path: '/',
      maxAge: 60 * 60 * 24 * 365, // 1 year
      sameSite: config.BASEROW_FRONTEND_SAME_SITE_COOKIE,
      secure,
    })
  }
}
