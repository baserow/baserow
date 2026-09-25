import { collatedStringCompare } from '@baserow/modules/core/utils/string'

/**
 * Selecting none or all of the application types both mean the user isn't
 * filtering, so the label and the filtering must agree on that rule.
 */
export function isTypeFilterActive(selectedTypes, applicationTypeCount) {
  return selectedTypes.length > 0 && selectedTypes.length < applicationTypeCount
}

export const SORT_BY_CREATED = 'created'
export const SORT_BY_LAST_VIEWED = 'last_viewed'
export const SORT_BY_NAME_ASC = 'name_asc'
export const SORT_BY_NAME_DESC = 'name_desc'

function compareByOrder(a, b) {
  return a.order - b.order
}

// Viewed items first, most recent first. Items the user never opened keep
// their manual order after them.
function compareByLastViewed(a, b) {
  if (a.last_viewed && b.last_viewed) {
    return Date.parse(b.last_viewed) - Date.parse(a.last_viewed)
  }
  if (a.last_viewed) {
    return -1
  }
  if (b.last_viewed) {
    return 1
  }
  return compareByOrder(a, b)
}

function compareByNameAsc(a, b) {
  return collatedStringCompare(a.name, b.name, 'ASC')
}

function compareByNameDesc(a, b) {
  return collatedStringCompare(a.name, b.name, 'DESC')
}

const COMPARATORS = {
  [SORT_BY_CREATED]: compareByOrder,
  [SORT_BY_LAST_VIEWED]: compareByLastViewed,
  [SORT_BY_NAME_ASC]: compareByNameAsc,
  [SORT_BY_NAME_DESC]: compareByNameDesc,
}

/**
 * @param {string} sortBy One of the `SORT_BY_*` constants.
 * @returns {function} A comparator for `Array.prototype.sort` over applications.
 */
export function getApplicationComparator(sortBy) {
  return COMPARATORS[sortBy] ?? compareByOrder
}

/**
 * For the flat search results, whose input is already grouped by workspace. A
 * per workspace `order` means nothing across workspaces, so never viewed
 * applications keep the grouping instead of interleaving by it.
 *
 * @param {string} sortBy One of the `SORT_BY_*` constants.
 * @returns {function} A comparator for a stable `Array.prototype.sort`.
 */
export function getSearchResultComparator(sortBy) {
  const comparator = getApplicationComparator(sortBy)
  if (sortBy !== SORT_BY_LAST_VIEWED) {
    return comparator
  }
  return (a, b) => (!a.last_viewed && !b.last_viewed ? 0 : comparator(a, b))
}

/**
 * @param {Array} applications The applications to inspect.
 * @returns {string|null} The most recent `last_viewed`, or `null` when none of
 *   them has been viewed.
 */
export function latestViewedOf(applications) {
  let latest = null
  for (const { last_viewed: lastViewed } of applications) {
    if (
      lastViewed &&
      (latest === null || Date.parse(lastViewed) > Date.parse(latest))
    ) {
      latest = lastViewed
    }
  }
  return latest
}

/**
 * Orders the workspace boxes consistently with their application cards. For
 * "last viewed" a workspace counts as viewed at the moment of its most recently
 * viewed application; workspaces without one keep their manual order at the end.
 *
 * @param {Array} workspaces The workspaces in their manual order, left untouched.
 * @param {string} sortBy One of the `SORT_BY_*` constants.
 * @param {function} applicationsOf Returns the applications of a workspace.
 * @returns {Array} A new, sorted array of workspaces.
 */
export function sortWorkspaces(workspaces, sortBy, applicationsOf) {
  if (sortBy === SORT_BY_CREATED) {
    return workspaces
  }
  const comparator = getApplicationComparator(sortBy)
  const keyed = workspaces.map((workspace) => ({
    workspace,
    name: workspace.name,
    order: workspace.order,
    last_viewed: latestViewedOf(applicationsOf(workspace)),
  }))
  return keyed.sort(comparator).map(({ workspace }) => workspace)
}
