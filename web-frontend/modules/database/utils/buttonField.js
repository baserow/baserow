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

// A database has no single entry point the way a builder does, so its
// integrations are fetched the first time an action editor asks for them.
// The request in flight is shared, and the entry dropped once it settles, so
// a failed one is asked again rather than remembered as an empty database.
const inFlightIntegrations = new Map()

/**
 * Fetches a database's integrations, at most once per database.
 *
 * Whether they have been loaded is remembered on the application itself, the
 * way the builder and automation do it, so a refetch that replaces the object
 * asks again.
 *
 * @param {Object} store The Vuex store.
 * @param {Number} applicationId The database whose integrations are wanted.
 * @return {Promise} Settles when the list is loaded, rejects when it is not.
 */
export function fetchIntegrationsOnce(store, applicationId) {
  const current = () => store.getters['application/get'](applicationId)
  if (current()?._integrationsLoadedOnce) {
    return Promise.resolve()
  }
  if (!inFlightIntegrations.has(applicationId)) {
    const request = (async () => {
      // Resolved from the store rather than captured, on both sides of the
      // await: `application/forceSetAll` replaces the object, and marking one
      // object loaded while filling another leaves the list on screen empty
      // and nothing to fetch it again.
      const application = current()
      if (!application) {
        return
      }
      await store.dispatch('integration/fetch', { application })
      const settled = current()
      if (!settled) {
        return
      }
      await store.dispatch('application/forceUpdate', {
        application: settled,
        data: { _integrationsLoadedOnce: true },
      })
    })()
    inFlightIntegrations.set(
      applicationId,
      request.finally(() => inFlightIntegrations.delete(applicationId))
    )
  }
  return inFlightIntegrations.get(applicationId)
}
