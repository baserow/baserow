import { defineNuxtPlugin } from '#imports'

const PARAMS = ['oauth2_status', 'oauth2_error', 'oauth2_integration']

/**
 * The OAuth2 callback sends the browser back to the page the connection was
 * started from with the outcome in the query string. Shown once as a toast,
 * then removed from the URL so a reload does not repeat it.
 */
export default defineNuxtPlugin((nuxtApp) => {
  if (import.meta.server) {
    return
  }
  nuxtApp.hook('app:mounted', () => {
    const url = new URL(window.location.href)
    const status = url.searchParams.get('oauth2_status')
    if (!status) {
      return
    }
    const error = url.searchParams.get('oauth2_error')
    PARAMS.forEach((param) => url.searchParams.delete(param))
    window.history.replaceState(window.history.state, '', url.toString())

    const store = nuxtApp.$store
    const i18n = nuxtApp.$i18n
    if (status === 'success') {
      store.dispatch('toast/success', {
        title: i18n.t('oauth2Result.successTitle'),
        message: i18n.t('oauth2Result.successMessage'),
      })
    } else {
      store.dispatch('toast/error', {
        title: i18n.t('oauth2Result.errorTitle'),
        message: error || i18n.t('oauth2Result.errorMessage'),
      })
    }
  })
})
