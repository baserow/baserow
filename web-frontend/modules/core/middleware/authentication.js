import {
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

  const userSession = to.query.user_session
  if (userSession) {
    await setUserSessionCookie(nuxtApp, userSession)
  }

  // token can be in the query string (SSO) or in the cookies (previous session)
  let refreshToken = to.query.token
  if (refreshToken) {
    await setToken(nuxtApp, refreshToken)
  } else {
    refreshToken = await getTokenIfEnoughTimeLeft(nuxtApp)
  }

  if (refreshToken) {
    try {
      await store.dispatch('auth/refresh', refreshToken)
    } catch (error) {
      if (error.response?.status === 401) {
        return navigateTo({ name: 'login' }, { external: true }) // force browser 302 redirect to get rid of the jwt cookie in the request headers
      }
    }
  }
})
