export const USER_SOURCE_COOKIE_TOKEN_NAME = 'user_source_token'
export const REFRESH_TOKEN_MAX_AGE = 60 * 60 * 24 * 7

export const getRefreshTokenCookieOptions = ({
  path = '/',
  sameSite,
  secure,
} = {}) => ({
  path,
  maxAge: REFRESH_TOKEN_MAX_AGE,
  sameSite,
  secure,
})
