/**
 * After a failed SSO login, the provider redirects back to the application with an
 * error code in a query parameter, for example
 * `saml_error__42=errorApplicationUserLimitReached`. Returns the first structured
 * error found for the given user sources without modifying the URL.
 *
 * @param {Object} $registry The registry used to resolve the auth provider types.
 * @param {Array} userSources The user sources whose auth providers must be checked.
 * @param {URL} url The callback URL to inspect.
 * @returns {{message: string, queryParamNames: string[]}|null}
 */
export const getLoginError = ($registry, userSources, url) => {
  for (const userSource of userSources) {
    for (const authProvider of userSource.auth_providers || []) {
      const callback = $registry
        .get('appAuthProvider', authProvider.type)
        .getAuthProviderCallback(userSource, url)
      if (callback?.error) {
        return {
          message: callback.error.message,
          queryParamNames: callback.queryParamNames,
        }
      }
    }
  }

  return null
}

/** Returns the first login error and removes its parameters from the browser URL. */
export const consumeLoginError = ($registry, userSources) => {
  if (typeof window === 'undefined') {
    return null
  }

  const url = new URL(window.location.href)
  const error = getLoginError($registry, userSources, url)
  if (!error) {
    return null
  }

  error.queryParamNames.forEach((name) => url.searchParams.delete(name))
  window.history.replaceState({}, document.title, url.toString())
  return error.message
}
