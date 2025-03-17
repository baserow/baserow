import {
  getTokenIfEnoughTimeLeft,
  setToken,
  setUserSessionCookie,
} from '@baserow/modules/core/utils/auth'

export default function ({ store, req, app, route, redirect }) {
  // If nuxt generate or already authenticated, pass this middleware
  if (
    (process.server && !req) ||
    store.getters['auth/isAuthenticated'] ||
    route.name === 'login'
  )
    return

  const userSession = route.query.user_session
  if (userSession) {
    setUserSessionCookie(app, userSession)
  }

  // check if the token is still valid in the cookies
  let refreshToken = getTokenIfEnoughTimeLeft(undefined, req)

  // if the token is not valid in the cookies, check if it is in the query string (SSO)
  if (!refreshToken && route.query.token) {
    refreshToken = route.query.token
    setToken(app, refreshToken)
  }

  if (refreshToken) {
    return store.dispatch('auth/refresh', refreshToken).catch((error) => {
      if (error.response?.status === 401) {
        return redirect({ name: 'login' })
      }
    })
  }
}
