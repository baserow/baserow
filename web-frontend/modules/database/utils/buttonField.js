import { notifyIf } from '@baserow/modules/core/utils/error'
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

// Keyed by store, not by application id alone: one server process renders
// every request, and a promise closed over one request's store must not be
// handed to another's.
const inFlightIntegrations = new WeakMap()

/**
 * Fetches a database's integrations, at most once per database. A database has
 * no single entry point the way a builder does, so the first editor to need
 * them asks. Loading is remembered on the application, so a refetch that
 * replaces it asks again, and a failure is reported here rather than by the
 * caller, since several callers can await one request.
 *
 * @param {Object} store The Vuex store.
 * @param {Number} applicationId The database whose integrations are wanted.
 * @return {Promise<Boolean>} Whether the list was loaded.
 */
export function fetchIntegrationsOnce(store, applicationId) {
  const current = () => store.getters['application/get'](applicationId)
  if (current()?._integrationsLoadedOnce) {
    return Promise.resolve(true)
  }
  if (!inFlightIntegrations.has(store)) {
    inFlightIntegrations.set(store, new Map())
  }
  const inFlight = inFlightIntegrations.get(store)
  if (!inFlight.has(applicationId)) {
    const request = (async () => {
      // Resolved on both sides of the await: `forceSetAll` replaces the
      // object, and filling one while marking another leaves both wrong.
      const application = current()
      if (!application) {
        return false
      }
      let loaded
      try {
        loaded = await store.dispatch('integration/fetch', { application })
      } catch (error) {
        // Once for the request, whoever is waiting on it.
        notifyIf(error, 'application')
        return false
      }
      // Backed off because the list changed under it, so what is there now is
      // not the whole list. Left unmarked, so the next ask fetches again.
      if (loaded === null) {
        return false
      }
      const settled = current()
      if (!settled) {
        return false
      }
      await store.dispatch('application/forceUpdate', {
        application: settled,
        data: { _integrationsLoadedOnce: true },
      })
      return true
    })()
    // Dropped once it settles, so a failed one is asked again.
    inFlight.set(
      applicationId,
      request.finally(() => inFlight.delete(applicationId))
    )
  }
  return inFlight.get(applicationId)
}
