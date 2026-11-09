/**
 * The private link of a template, `/template/<slug>/private-link/<token>`,
 * carries its token in the path, like the slug of a shared view. While the page of
 * the link is open, the token is sent with every API request in a header, like the
 * token of a password protected public view.
 */
export const PRIVATE_LINK_TOKEN_HEADER = 'Baserow-Template-Authorization'
const TOKEN_RE = /^[0-9a-f]{64}$/

/**
 * Whether the route is the page of a private link. The router matches the path
 * ignoring case, but a token is lowercase.
 */
export const isPrivateLinkPage = (route) =>
  route.name === 'template-private-link' && TOKEN_RE.test(route.params.token)

/**
 * The token of the private link whose page is open, if any.
 */
export const getOpenPrivateLinkToken = (nuxtApp) => {
  const route = nuxtApp.$router.currentRoute.value
  return isPrivateLinkPage(route) ? route.params.token : null
}

/**
 * An axios request interceptor that sends the token of the private link whose
 * page is open. A request that sends a token already, of a link opened before,
 * keeps it.
 */
export const addPrivateLinkTokenHeader = (nuxtApp) => (config) => {
  const token = getOpenPrivateLinkToken(nuxtApp)
  config.headers ||= {}
  if (token && !config.headers[PRIVATE_LINK_TOKEN_HEADER]) {
    config.headers[PRIVATE_LINK_TOKEN_HEADER] = token
  }
  return config
}

const TOKEN_IN_URL_RE =
  /(private-link(?:\/|%(?:25)*2F))(?:[0-9a-f]|%(?:25)*[0-9a-f]{2}){64}/gi

/**
 * Whether the URL carries the token of a private link.
 */
export const carriesPrivateLinkToken = (url) =>
  typeof url === 'string' && url.search(TOKEN_IN_URL_RE) !== -1

const redact = (value) => {
  if (typeof value === 'string') {
    return value.replace(TOKEN_IN_URL_RE, '$1[redacted]')
  }
  if (Array.isArray(value)) {
    return value.map(redact)
  }
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

/**
 * Adds the session replay of Sentry, unless the page carries the token of a
 * private link, and stops it for good before a navigation to one. Recordings
 * skip `beforeSend`, so their URLs can't be redacted.
 *
 * @param {object} options
 * @param {object} options.router The router of the app.
 * @param {Function} options.loadReplayIntegration Resolves to the
 *   `replayIntegration` of `@sentry/replay`, which is only downloaded when needed.
 * @param {Function} options.addIntegration Adds the integration to Sentry.
 * @param {object} options.replayOptions The options of the integration.
 */
export const addReplayOutsidePrivateLinks = async ({
  router,
  loadReplayIntegration,
  addIntegration,
  replayOptions,
}) => {
  if (carriesPrivateLinkToken(window.location.href)) {
    return
  }
  let replay = null
  let privateLinkOpened = false
  router.beforeEach((to) => {
    if (carriesPrivateLinkToken(to.fullPath)) {
      privateLinkOpened = true
      replay?.stop({ flush: false })
    }
  })
  const replayIntegration = await loadReplayIntegration()
  if (privateLinkOpened || carriesPrivateLinkToken(window.location.href)) {
    return
  }
  replay = replayIntegration(replayOptions)
  addIntegration(replay)
}
