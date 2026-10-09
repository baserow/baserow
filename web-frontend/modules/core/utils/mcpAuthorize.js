import authenticated from '@baserow/modules/core/middleware/authenticated'

/**
 * Route middleware for the MCP consent page. A fatal authorize error is shown
 * straight away, so a signed-out user isn't sent through the login first.
 */
export function authenticatedUnlessError(to, from) {
  if (to.query.error) {
    return
  }
  return authenticated(to, from)
}
