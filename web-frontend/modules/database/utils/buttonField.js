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
 * Only used so a relative URL parses at all. Its protocol is an allowed one,
 * so relative URLs keep passing through.
 */
const RELATIVE_URL_BASE = 'http://baserow.invalid'

/**
 * Returns the URL when its protocol is allowed, and an empty string when it is
 * not. A URL without a protocol is relative and passes through. This is what
 * keeps a `javascript:` URL built by a formula from being navigated to.
 *
 * The protocol comes from `new URL()`, the same WHATWG parse the browser runs
 * when the URL reaches `window.location`. A regex over the raw string decides
 * differently from that parser: the parser first strips leading C0 control
 * characters, so `\x01javascript:alert(1)` looks relative to a regex while the
 * browser still runs it as `javascript:`.
 *
 * The original string is returned rather than the parsed one, because parsing
 * normalises and re-encodes a URL the formula deliberately built.
 */
export function urlWithAllowedProtocol(url) {
  let protocol
  try {
    protocol = new URL(url, RELATIVE_URL_BASE).protocol
  } catch (error) {
    // Not something the browser could navigate to either.
    return ''
  }
  return ALLOWED_BUTTON_URL_PROTOCOLS.includes(protocol.toLowerCase())
    ? url
    : ''
}
