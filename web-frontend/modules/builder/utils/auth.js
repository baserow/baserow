/**
 * After a failed SSO login, the provider redirects back to the application with an
 * error code in a query parameter, for example
 * `saml_error__42=errorApplicationUserLimitReached`. Returns the translated message
 * of the first error found for the given user sources and removes the parameter from
 * the URL so it doesn't linger on refresh. Returns `null` when there is nothing to
 * report.
 *
 * The query string is read from `window.location` and not from the router route
 * because the parameter is removed with `history.replaceState`, which doesn't update
 * the route.
 *
 * @param {Object} $registry The registry used to resolve the auth provider types.
 * @param {Array} userSources The user sources whose auth providers must be checked.
 * @returns {string|null}
 */
export const consumeLoginError = ($registry, userSources) => {
  if (typeof window === 'undefined') {
    return null
  }

  const query = Object.fromEntries(new URLSearchParams(window.location.search))

  for (const userSource of userSources) {
    for (const authProvider of userSource.auth_providers || []) {
      const message = $registry
        .get('appAuthProvider', authProvider.type)
        .getLoginError(userSource, { query })
      if (message) {
        return message
      }
    }
  }

  return null
}
