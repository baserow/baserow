import {
  getRefreshTokenSessionId,
  getTokenIfEnoughTimeLeft,
  setToken,
  setUserSessionCookie,
} from '@baserow/modules/core/utils/auth'

export default defineNuxtRouteMiddleware(async (to) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store
  const event = import.meta.server ? useRequestEvent() : null

  // If nuxt generate or already authenticated, pass this middleware
  if ((import.meta.server && !event) || store.getters['auth/isAuthenticated']) {
    return
  }

  // token can be in the query string (SSO) or in the cookies (previous session)
  const cookieToken = await getTokenIfEnoughTimeLeft(nuxtApp)
  let refreshToken = to.query.token
  const sessionId = getRefreshTokenSessionId(refreshToken)
  if (
    sessionId &&
    cookieToken &&
    sessionId === getRefreshTokenSessionId(cookieToken)
  ) {
    // Reloading a page that still has the token in its URL. It has been
    // rotated since, and using it again would sign the session off.
    refreshToken = cookieToken
  } else if (refreshToken) {
    await setToken(nuxtApp, refreshToken)
    if (to.query.user_session) {
      await setUserSessionCookie(nuxtApp, to.query.user_session)
    }
  } else {
    refreshToken = cookieToken
  }

  if (refreshToken) {
    try {
      await store.dispatch('auth/refresh', refreshToken)
    } catch (error) {
      if (error.response?.status === 401) {
        return nuxtApp.runWithContext(() =>
          navigateTo({ name: 'login' }, { external: true })
        ) // force browser 302 redirect to get rid of the jwt cookie in the request headers
      }
    }
  }
})
