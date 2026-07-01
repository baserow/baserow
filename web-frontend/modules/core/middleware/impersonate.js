import UserService from '@baserow/modules/core/services/admin/users'

export const impersonateMiddleware = async (to, { nuxtApp }) => {
  const store = nuxtApp.$store

  // If the query param is not provided, we don't want to do anything.
  if (!Object.prototype.hasOwnProperty.call(to.query, '__impersonate-user')) {
    return
  }

  // No session yet — `authentication` middleware normally redirects first,
  // but bail if it didn't so we don't fire a request that will 401.
  if (!store.getters['auth/isAuthenticated']) {
    return
  }

  const userId = to.query['__impersonate-user']

  // Already impersonating this user. A redirect after impersonation (e.g.
  // `dashboardRedirect`) makes Nuxt re-run middlewares with the impersonated
  // user in the store; without this guard we'd call the endpoint again as
  // that user.
  if (String(store.getters['auth/getUserId']) === String(userId)) {
    return
  }

  // Request the impersonate user data, this contains the `token` and `user` object.
  // This is needed to impersonate the user.
  const { data } = await UserService(nuxtApp.$client).impersonate(userId)

  // Override the existing user data based on the response of the impersonate endpoint.
  store.dispatch('auth/forceSetUserData', data)

  // Make sure that the auth doesn't override the JWT token cookie because we want
  // the admin one to persist.
  store.dispatch('auth/preventSetToken')

  // Set the impersonating state to true so that the warning in the top left corner
  // is visible.
  store.dispatch('impersonating/setImpersonating', true)
}

/**
 * We only want to allow impersonation when a page loads for the first time because
 * on first load several endpoints are called to fetch initial data like workspace,
 * applications, etc. Starting the impersonation when the page first loads, makes
 * sure that we never have to take this situation into account because it only
 * happens on first page load before everything is fetched.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  if (!import.meta.server) return

  const nuxtApp = useNuxtApp()
  return impersonateMiddleware(to, { nuxtApp })
})
