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
 * Returns true when the error says that the requested page does not exist. A
 * visitor gets this error when the site has been published again while their tab
 * was open, because each publish gives every page a new id.
 */
export const isPageDoesNotExistError = (error) =>
  error?.response?.status === 404 &&
  error.response.data?.error === 'ERROR_PAGE_DOES_NOT_EXIST'

/**
 * Reloads the app on the given path so the visitor gets the newly published version
 * of the site. The hash is dropped: assigning a URL that only differs from the
 * current one by its hash makes the browser jump to the fragment instead of loading
 * the page again.
 */
export const reloadPublishedSite = (fullPath) =>
  reloadNuxtApp({ path: fullPath.split('#')[0], force: true })
