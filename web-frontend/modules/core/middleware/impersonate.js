import UserService from '@baserow/modules/core/services/admin/users'

/**
 * Core impersonate logic, extracted so it can be unit tested without going
 * through Nuxt's auto-imports and the SSR-only guard.
 */
export const impersonateMiddleware = async (to, { nuxtApp }) => {
  const store = nuxtApp.$store

  // If the query param is not provided, we don't want to do anything.
  if (!Object.prototype.hasOwnProperty.call(to.query, '__impersonate-user')) {
    return
  }

  // The impersonate endpoint requires a staff user. If the SSR auth state
  // hasn't been established yet (e.g. the refresh token cookie is missing or
  // too close to expiry for `authentication` middleware to refresh), or the
  // current user isn't staff, calling the endpoint would always yield a 403.
  // Bail out early so we don't fire a guaranteed-failing request.
  if (
    !store.getters['auth/isAuthenticated'] ||
    !store.getters['auth/isStaff']
  ) {
    return
  }

  const userId = to.query['__impersonate-user']

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
