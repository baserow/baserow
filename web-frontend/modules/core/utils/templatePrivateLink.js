/**
 * The private link of a template, `/template/<slug>/private-link/<token>`,
 * carries its token in the path, like the slug of a shared view. While the page of
 * the link is open, the token is sent with every API request in a header, like the
 * token of a password protected public view.
 */
export const PRIVATE_LINK_HEADER = 'Baserow-Template-Authorization'
const TOKEN_RE = /^[0-9a-f]{64}$/

/**
 * The token of the private link whose page is open, if any.
 */
export const getOpenPrivateLinkToken = (nuxtApp) => {
  const { name, params } = nuxtApp.$router.currentRoute.value
  return name === 'template-private-link' && TOKEN_RE.test(params.token)
    ? params.token
    : null
}

/**
 * An axios request interceptor that sends the token of the private link whose
 * page is open. A request that sends a token already, of a link opened before,
 * keeps it.
 */
export const addPrivateLinkHeader = (nuxtApp) => (config) => {
  const token = getOpenPrivateLinkToken(nuxtApp)
  config.headers ||= {}
  if (token && !config.headers[PRIVATE_LINK_HEADER]) {
    config.headers[PRIVATE_LINK_HEADER] = token
  }
  return config
}

// The token in the path of the link, or in the `original` query of a sign-in page
// leading back to it.
const TOKEN_IN_URL_RE = /(private-link(?:\/|%2F))[0-9a-f]{64}/gi

const redact = (value) => {
  if (typeof value === 'string') {
    return value.replace(TOKEN_IN_URL_RE, '$1[redacted]')
  }
  if (Array.isArray(value)) {
    return value.map(redact)
  }
  // Only plain objects, so that a date or an error stays what it is.
  if (value === null || typeof value !== 'object') {
    return value
  }
  const proto = Object.getPrototypeOf(value)
  if (proto === Object.prototype || proto === null) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, redact(item)])
    )
  }
  return value
}

/**
 * A PostHog `before_send` and Sentry `beforeSend` hook that replaces the token of
 * a private link in the URLs an event carries, so that it doesn't reach analytics
 * or error reports.
 */
export const redactPrivateLinkTokens = (event) => event && redact(event)
