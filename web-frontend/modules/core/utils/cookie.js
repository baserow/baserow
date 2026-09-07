import { isSecureURL } from './string'

export const userSourceCookieTokenName = 'user_source_token'
export const refreshTokenMaxAge = 60 * 60 * 24 * 7

export const getCookieName = (config, key) => {
  return `${config.public.baserowFrontendCookiePrefix || ''}${key}`
}

export const getTokenCookieOptions = (config, configuration = {}) => ({
  path: configuration.path || '/',
  maxAge: refreshTokenMaxAge,
  sameSite:
    configuration.sameSite || config.public.baserowFrontendSameSiteCookie,
  secure:
    configuration.secure ??
    isSecureURL(configuration.cookieUrl || config.public.publicWebFrontendUrl),
})
