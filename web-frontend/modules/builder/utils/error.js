import { reloadNuxtApp } from '#app'

export const handleDispatchError = (err, instance, context = '') => {
  const $t = (...params) => {
    return !instance.$t ? instance.$i18n.t(...params) : instance.$t(...params)
  }

  const $store = instance.store || instance.$store

  let toastTitle = $t('builderToast.defaultTitle')
  let toastMessage = $t('builderToast.defaultMessage')

  const errorType = err.response?.data?.error

  switch (errorType) {
    case 'ERROR_SERVICE_INVALID_DISPATCH_CONTEXT':
      toastTitle = $t('builderToast.invalidContextTitle')
      toastMessage = $t('builderToast.invalidContextMessage')
      break
    case 'ERROR_SERVICE_INVALID_DISPATCH_CONTEXT_CONTENT':
      toastTitle = $t('builderToast.InvalidContentTitle')
      toastMessage = $t('builderToast.invalidContentMessage')
      break
    case 'ERROR_SERVICE_IMPROPERLY_CONFIGURED':
      toastTitle = $t('builderToast.serviceMisconfiguredTitle')
      toastMessage = $t('builderToast.serviceMisconfiguredMessage')
      break
  }
  return $store.dispatch('builderToast/error', {
    title: toastTitle,
    message: `${context}${toastMessage}`,
    details: err.response?.data?.detail,
  })
}

/**
 * The "does not exist" errors a visitor gets when the site has been published again
 * while their tab was open. Each publish gives every page, element, data source,
 * workflow action and user source a new id, so the ids the tab still has are gone.
 * `ERROR_DATA_DOES_NOT_EXIST` isn't listed because it's about a missing row, which
 * can happen on an up to date site too.
 */
const STALE_PUBLISHED_ID_ERRORS = new Set([
  'ERROR_PAGE_DOES_NOT_EXIST',
  'ERROR_ELEMENT_DOES_NOT_EXIST',
  'ERROR_DATA_SOURCE_DOES_NOT_EXIST',
  'ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST',
  'ERROR_USER_SOURCE_DOES_NOT_EXIST',
])

/**
 * Returns true when the error says that an object of the published site doesn't
 * exist anymore, which means the site has been published again.
 */
export const isStalePublishedIdError = (error) =>
  error?.response?.status === 404 &&
  STALE_PUBLISHED_ID_ERRORS.has(error.response.data?.error)

/**
 * The stale errors that come from something the visitor did, like submitting a form
 * or logging in. What they typed is lost by the reload, so the reloaded page tells
 * them to try again.
 */
const VISITOR_ACTION_STALE_ERRORS = new Set([
  'ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST',
  'ERROR_USER_SOURCE_DOES_NOT_EXIST',
])

/**
 * Returns true when the stale error comes from something the visitor did.
 */
export const isVisitorActionStaleError = (error) =>
  isStalePublishedIdError(error) &&
  VISITOR_ACTION_STALE_ERRORS.has(error.response.data.error)

const RELOAD_GUARD_KEY = 'baserow:builder:stalePublishedSiteReload'
const RELOAD_GUARD_TTL = 10000
const RELOAD_NOTICE_KEY = 'baserow:builder:stalePublishedSiteReloadNotice'

// Whether this document has already started a reload. It's reset by the reload
// itself, as the new document loads this module again.
let reloadStarted = false

/**
 * Reloads the app on the given path so the visitor gets the newly published version
 * of the site. The hash is dropped: assigning a URL that only differs from the
 * current one by its hash makes the browser jump to the fragment instead of loading
 * the page again.
 *
 * Requests sent in parallel with the stale ids all fail, so once this document has
 * started a reload, later calls only report that the reload happens.
 *
 * A freshly loaded page has the current ids, so it shouldn't get the error again.
 * If it does anyway (e.g. the public cache wasn't cleared after the publish because
 * of a Redis error, or a proxy serves a cached page), we don't reload a second time
 * within `RELOAD_GUARD_TTL` so a bug can't turn into a reload loop. Returns whether
 * the reload happens.
 *
 * With `notify`, the reloaded page tells the visitor that the site was updated, see
 * `consumeStaleSiteReloadNotice`.
 */
export const reloadPublishedSite = (fullPath, { notify = false } = {}) => {
  if (reloadStarted) {
    if (notify) {
      setReloadNotice()
    }
    return true
  }
  try {
    const lastReload = Number(sessionStorage.getItem(RELOAD_GUARD_KEY))
    if (lastReload && Date.now() - lastReload < RELOAD_GUARD_TTL) {
      return false
    }
    sessionStorage.setItem(RELOAD_GUARD_KEY, String(Date.now()))
  } catch {
    // The storage can be blocked. Reloading is still the best way out.
  }
  if (notify) {
    setReloadNotice()
  }
  reloadNuxtApp({ path: fullPath.split('#')[0], force: true })
  reloadStarted = true
  return true
}

const setReloadNotice = () => {
  try {
    sessionStorage.setItem(RELOAD_NOTICE_KEY, '1')
  } catch {
    // Without storage the reloaded page can't show the notice, which is fine.
  }
}

/**
 * Returns true once after a reload by `reloadPublishedSite` with `notify`, so the
 * reloaded page can tell the visitor to try again.
 */
export const consumeStaleSiteReloadNotice = () => {
  try {
    if (sessionStorage.getItem(RELOAD_NOTICE_KEY) === null) {
      return false
    }
    sessionStorage.removeItem(RELOAD_NOTICE_KEY)
    return true
  } catch {
    return false
  }
}
