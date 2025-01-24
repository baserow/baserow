import UserService from '@baserow/modules/core/services/admin/users'

/**
 * We only want to allow impersonation when a page loads for the first time because
 * on first load several endpoints are called to fetch initial data like workspace,
 * applications, etc. Starting the impersonation when the page first loads, makes
 * sure that we never have to take this situation into account because it only
 * happens on first page load before everything is fetched.
 */
export default async function ({ store, req, app, route }) {
  if (!req) return

  // If the query param is not provided, we don't want to do anything.
  if (
    !Object.prototype.hasOwnProperty.call(route.query, '__impersonate-user')
  ) {
    return
  }

  const userId = route.query['__impersonate-user']

  // Request the impersonate user data, this contains the `token` and `user` object.
  // This is needed to impersonate the user.
  const { data } = await UserService(app.$client).impersonate(userId)

  // Override the existing user data based on the response of the impersonate endpoint.
  store.dispatch('auth/forceSetUserData', data)

  // Make sure that the auth doesn't override the JWT token cookie because we want
  // the admin one to persist.
  store.dispatch('auth/preventSetToken')

  // Set the impersonating state to true so that the warning in the top left corner
  // is visible.
  store.dispatch('impersonating/setImpersonating', true)
}
