export const getCookieName = (config, key) => {
  return `${config.public.baserowFrontendCookiePrefix || ''}${key}`
}
