/**
 * Constants related to Visibility and Roles
 */
export const VISIBILITY_ALL = 'all'
export const VISIBILITY_NOT_LOGGED = 'not-logged'
export const VISIBILITY_LOGGED_IN = 'logged-in'
export const ROLE_TYPE_ALLOW_ALL = 'allow_all'
export const ROLE_TYPE_ALLOW_EXCEPT = 'allow_all_except'
export const ROLE_TYPE_DISALLOW_EXCEPT = 'disallow_all_except'
export const DEFAULT_USER_ROLE_PREFIX = '__user_source_'

/**
 * Describes the data available to a formula relative to its target element.
 *
 * This is intentionally a compound object so data providers can interpret the
 * options that apply to their data, including whether they can read the target
 * element, its descendants, or its schema properties.
 */
const DEFAULT_DATA_SCOPE = {
  includeTargetElement: false,
  includeTargetDescendants: false,
  includeTargetSchemaProperties: false,
}

export const DATA_SCOPES = {
  EXCLUDE_TARGET_SUBTREE: { ...DEFAULT_DATA_SCOPE },
  INCLUDE_TARGET_ELEMENT: {
    ...DEFAULT_DATA_SCOPE,
    includeTargetElement: true,
    includeTargetDescendants: true,
    includeTargetSchemaProperties: true,
  },
  INCLUDE_TARGET_DATA_SOURCE: {
    ...DEFAULT_DATA_SCOPE,
    includeTargetElement: true,
    includeTargetDescendants: true,
  },
}
