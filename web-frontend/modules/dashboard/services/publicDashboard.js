/**
 * The endpoints of a publicly shared dashboard. They are addressed by the public
 * slug of the dashboard instead of its id and work without being logged in. A
 * password protected dashboard additionally needs the token that the `auth`
 * endpoint hands out for the right password.
 */

export const PUBLIC_DASHBOARD_AUTHORIZATION_HEADER =
  'Baserow-Dashboard-Authorization'

const withAuthToken = (authToken) => {
  if (!authToken) {
    return {}
  }
  return {
    headers: { [PUBLIC_DASHBOARD_AUTHORIZATION_HEADER]: `JWT ${authToken}` },
  }
}

export default (client) => {
  return {
    fetchInfo(slug, authToken = null) {
      return client.get(`/dashboard/public/${slug}/`, withAuthToken(authToken))
    },
    dispatch(slug, dataSourceId, authToken = null) {
      return client.post(
        `/dashboard/public/${slug}/data-sources/${dataSourceId}/dispatch/`,
        null,
        withAuthToken(authToken)
      )
    },
    fetchAuthInfo(slug) {
      return client.get(`/dashboard/public/${slug}/auth/`)
    },
    auth(slug, password) {
      return client.post(`/dashboard/public/${slug}/auth/`, { password })
    },
  }
}
