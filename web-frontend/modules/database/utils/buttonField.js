// Recorded for a table whose fields could not be fetched. Kept apart from an
// empty list, which is a table that really has no fields, and from an absent
// entry, which is a table nothing has fetched yet.
export const FIELDS_UNAVAILABLE = Symbol('fieldsUnavailable')

/**
 * Percent-encodes the whitespace in a resolved URL. Row values often contain
 * spaces, which our URL validation rejects. Only whitespace is touched, or we
 * would mangle or double-encode the rest.
 */
export function encodeUrlWhitespace(url) {
  return url.replace(/\s/g, (character) => encodeURIComponent(character))
}

/**
 * Mirrors the builder's `ALLOWED_LINK_PROTOCOLS`, duplicated so this module
 * does not depend on the builder module.
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
 * Returns the URL when its protocol is allowed and an empty string when it is
 * not, which is what keeps a formula-built `javascript:` URL from being
 * navigated to. A URL without a protocol is relative and passes through.
 *
 * The protocol comes from `new URL()`, the same parse the browser runs, rather
 * than a regex: the parser strips leading C0 controls first, so a regex would
 * read `\x01javascript:` as relative while the browser still runs it.
 *
 * The original string is returned, since parsing re-encodes what the formula
 * deliberately built.
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
