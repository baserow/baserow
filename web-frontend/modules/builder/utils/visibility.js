import {
  VISIBILITY_ALL,
  ROLE_TYPE_ALLOW_EXCEPT,
  ROLE_TYPE_DISALLOW_EXCEPT,
  ROLE_TYPE_ALLOW_ALL,
} from '@baserow/modules/builder/constants'

/**
 * Evaluates the Page's visibility settings and the user's role. Returns true
 * if the user is allowed to view the page. Otherwise, returns false.
 *
 * @param {Object} user The user object.
 * @param {Boolean} isAuthenticated Whether the user is authenticated.
 * @param {Object} page The Page to be evaluated.
 * @returns {Boolean} True if the user is allowed to view the page, false otherwise.
 */
export function userCanViewPage(user, isAuthenticated, page) {
  if (page.visibility === VISIBILITY_ALL) {
    return true
  }

  // If visibility is 'logged-in' (i.e. not 'all') *and* the user isn't
  // authenticated, disallow access.
  if (!isAuthenticated) {
    return false
  }

  if (page.role_type === ROLE_TYPE_ALLOW_EXCEPT) {
    // Allow if the user's role isn't explicitly excluded
    return !page.roles.includes(user.role)
  } else if (page.role_type === ROLE_TYPE_DISALLOW_EXCEPT) {
    // Allow if the user's role is explicitly included
    return page.roles.includes(user.role)
  } else if (page.role_type === ROLE_TYPE_ALLOW_ALL) {
    // Allow if there are no page level role restrictions
    return true
  }

  // Disallow access to the page by default
  return false
}
