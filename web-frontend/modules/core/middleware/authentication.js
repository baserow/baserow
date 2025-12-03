import {
  getTokenIfEnoughTimeLeft,
  setToken,
  setUserSessionCookie,
} from '@baserow/modules/core/utils/auth'

export default defineNuxtRouteMiddleware(async (to) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store
  const event = process.server ? useRequestEvent() : null

  // If nuxt generate or already authenticated, pass this middleware
  if ((process.server && !event) || store.getters['auth/isAuthenticated']) {
    return
  }

  const userSession = to.query.user_session
  if (userSession) {
    setUserSessionCookie(nuxtApp, userSession)
  }

  // token can be in the query string (SSO) or in the cookies (previous session)
  let refreshToken = to.query.token
  if (refreshToken) {
    setToken(nuxtApp, refreshToken)
  } else {
    refreshToken = getTokenIfEnoughTimeLeft(nuxtApp)
  }

  if (refreshToken) {
    try {
      await store.dispatch('auth/refresh', refreshToken)
    } catch (error) {
      if (error.response?.status === 401) {
        return navigateTo({ name: 'login' })
      }
    }
  }
})

/*
Previous Nuxt 2 middleware:
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
*/
