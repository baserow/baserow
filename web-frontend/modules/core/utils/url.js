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

export function ensureUrlProtocol(value) {
  const protocolRegex = /^[a-zA-Z]+:\/\//
  if (!protocolRegex.test(value)) {
    return `https://${value}`
  }
  return value
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
