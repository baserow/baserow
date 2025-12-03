import { isSecureURL } from '@baserow/modules/core/utils/string'
import jwtDecode from 'jwt-decode'
import { getDomain } from 'tldjs'
import { useCookie, useRuntimeConfig } from '#imports'

const cookieTokenName = 'jwt_token'
export const userSourceCookieTokenName = 'user_source_token'
export const userSessionCookieName = 'user_session'
const refreshTokenMaxAge = 60 * 60 * 24 * 7

export const setToken = (
  appOrContext, // Ignored in Nuxt 3, kept for compatibility
  token,
  key = cookieTokenName,
  configuration = { sameSite: null }
) => {
  const config = useRuntimeConfig()
  const secure = isSecureURL(config.public.publicWebFrontendUrl)
  const cookie = useCookie(key, {
    path: '/',
    maxAge: refreshTokenMaxAge,
    sameSite:
      configuration.sameSite || config.public.baserowFrontendSameSiteCookie,
    secure,
  })
  cookie.value = token
}

/**
 * Sets a session cookie in the browser to store the user's signed session payload upon
 * login. This cookie facilitates backend authentication for GET requests, such as
 * downloading files with the secure_file_serve feature, when the Authorization header
 * is unavailable. The payload includes a token hash to invalidate the cookie upon
 * logout.
 *
 * @param {*} app: the nuxt app instance
 * @param {*} signedUserSession: the signed user session payload to be stored in the
 * cookie
 * @param {*} key: the cookie name
 * @param {*} configuration: the configuration object with the sameSite key
 * @returns
 */
export const setUserSessionCookie = (
  appOrContext, // Ignored
  signedUserSession,
  key = userSessionCookieName,
  configuration = { sameSite: null }
) => {
  const config = useRuntimeConfig()
  const secure = isSecureURL(config.public.publicWebFrontendUrl)

  // To make the cookie available to all subdomains, set the domain to the top-level
  // domain. This is necessary for the secure_file_serve feature to work across
  // subdomains, as when the backend serves files from a different subdomain from the
  // frontend. The top-level domain is extracted from the backend URL.
  // NOTE: For security reasons, it's not possible to set a cookie for a different
  // domain, so this won't work if the frontend and backend are on different domains.
  const topLevelDomain = getDomain(config.public.publicBackendUrl)

  const cookie = useCookie(key, {
    path: '/',
    maxAge: refreshTokenMaxAge,
    sameSite:
      configuration.sameSite || config.public.baserowFrontendSameSiteCookie,
    secure,
    domain: topLevelDomain,
  })
  cookie.value = signedUserSession
}

export const unsetToken = (appOrContext, key = cookieTokenName) => {
  const cookie = useCookie(key)
  cookie.value = null
}

export const unsetUserSessionCookie = (
  appOrContext,
  key = userSessionCookieName
) => {
  const cookie = useCookie(key)
  cookie.value = null
}

export const getToken = (appOrContext, key = cookieTokenName) => {
  const cookie = useCookie(key)
  return cookie.value
}

export const getTokenIfEnoughTimeLeft = (
  appOrContext,
  key = cookieTokenName
) => {
  const token = getToken(appOrContext, key)
  const now = Math.ceil(new Date().getTime() / 1000)

  let data
  try {
    data = jwtDecode(token)
  } catch (error) {
    return null
  }
  // Return the token if it is still valid for more of the 10% of the lifespan.
  return data && (data.exp - now) / (data.exp - data.iat) > 0.1 ? token : null
}

export const logoutAndRedirectToLogin = (
  router,
  store,
  showSessionExpiredToast = false,
  showPasswordChangedToast = false,
  invalidateToken = false
) => {
  if (showPasswordChangedToast) {
    store.dispatch('auth/forceLogoff')
  } else {
    store.dispatch('auth/logoff', { invalidateToken })
  }
  router.push({ name: 'login', query: { noredirect: null } }).then(() => {
    if (showSessionExpiredToast) {
      store.dispatch('toast/setUserSessionExpired', true)
    } else if (showPasswordChangedToast) {
      store.dispatch('toast/setUserPasswordChanged', true)
    }
    store.dispatch('auth/clearAllStoreUserData')
  })
}
