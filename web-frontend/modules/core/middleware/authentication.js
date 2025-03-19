import {
  getTokenIfEnoughTimeLeft,
  setToken,
  setUserSessionCookie,
} from '@baserow/modules/core/utils/auth'

export default function ({ store, req, app, route, redirect }) {
  // If nuxt generate or already authenticated, pass this middleware
  if ((process.server && !req) || store.getters['auth/isAuthenticated']) return

  const userSession = route.query.user_session
  if (userSession) {
    setUserSessionCookie(app, userSession)
  }

  // token can be in the query string (SSO) or in the cookies (previous session)
  let refreshToken = route.query.token
  if (refreshToken) {
    setToken(app, refreshToken)
  } else {
    refreshToken = getTokenIfEnoughTimeLeft(app)
  }

  if (refreshToken) {
    return store.dispatch('auth/refresh', refreshToken).catch((error) => {
      if (error.response?.status === 401) {
        return redirect({ name: 'login' })
      }
    })
  }
}
