/**
 * Percent-encodes the whitespace in a resolved URL. Row values often contain
 * spaces and browsers accept them by encoding, but our URL validation does
 * not. Only whitespace is touched: anything more would mangle the URL
 * structure the formula builds, and would double-encode a value the user
 * already escaped with `encode_uri_component()`.
 */
export function encodeUrlWhitespace(url) {
  return url.replace(/\s/g, (character) => encodeURIComponent(character))
}

/**
 * The protocols a button is allowed to navigate to. Mirrors the builder's
 * `ALLOWED_LINK_PROTOCOLS`, kept here so the database module does not depend
 * on the builder module.
 */
export const ALLOWED_BUTTON_URL_PROTOCOLS = [
  'ftp:',
  'ftps:',
  'ftpes:',
  'http:',
  'https:',
  'mailto:',
  'sftp:',
  'sms:',
  'tel:',
]

/**
 * Returns the URL when its protocol is allowed, and an empty string when it is
 * not. A URL without a protocol is relative and passes through. This is what
 * keeps a `javascript:` URL built by a formula from being navigated to.
 */
export function urlWithAllowedProtocol(url) {
  if (!/^[A-Za-z]+:/.test(url)) {
    return url
  }
  const lowerCased = url.toLowerCase()
  const allowed = ALLOWED_BUTTON_URL_PROTOCOLS.some((protocol) =>
    lowerCased.startsWith(protocol)
  )
  return allowed ? url : ''
}
