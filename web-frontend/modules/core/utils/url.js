export function isRelativeUrl(url) {
  const absoluteUrlRegExp = /^(?:[a-z+]+:)?\/\//i
  return !absoluteUrlRegExp.test(url)
}

export function addQueryParamsToRedirectUrl(url, params) {
  const parsedUrl = new URL(url)

  for (const [key, value] of Object.entries(params)) {
    if (['language'].includes(key)) {
      parsedUrl.searchParams.append(key, value)
    }
  }

  if (params.original && isRelativeUrl(params.original)) {
    parsedUrl.searchParams.append('original', params.original)
  }

  if (params.invitationToken) {
    parsedUrl.searchParams.append(
      'workspace_invitation_token',
      params.invitationToken
    )
  }

  return parsedUrl.toString()
}

const SAFE_URL_PROTOCOLS = [
  'http:',
  'https:',
  'ftp:',
  'ftps:',
  'mailto:',
  'tel:',
]

export function getUrlScheme(value) {
  // Strip chars browsers ignore, so `java\tscript:` still reads as `javascript:`.
  // eslint-disable-next-line no-control-regex
  const stripped = String(value ?? '').replace(/[\x00-\x20]/g, '')
  const match = stripped.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/)
  return match ? `${match[1].toLowerCase()}:` : null
}

export function ensureUrlProtocol(value) {
  const scheme = getUrlScheme(value)
  if (scheme && SAFE_URL_PROTOCOLS.includes(scheme)) {
    return value
  }
  // Protocol-relative URLs only need the scheme, not another `//`.
  if (String(value).startsWith('//')) {
    return `https:${value}`
  }
  // Force https so an unsafe scheme (javascript:, data:) can't execute as a URI.
  return `https://${value}`
}

/**
 * Parses a comma-separated list of URLs and extracts their hostnames.
 * @param {string} urlsString - Comma-separated list of URLs
 * @returns {string[]} Array of hostnames extracted from valid URLs
 */
export function parseHostnamesFromUrls(urlsString) {
  if (!urlsString) return []

  return urlsString
    .split(',')
    .map((url) => url.trim())
    .filter((url) => url !== '')
    .map((url) => {
      try {
        return new URL(url).hostname
      } catch (e) {
        console.warn(`Invalid URL in BASEROW_EXTRA_PUBLIC_URLS: ${url}`)
        return null
      }
    })
    .filter((hostname) => hostname !== null)
}
