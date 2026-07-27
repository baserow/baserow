import { makeRefreshAuthInterceptor } from '@baserow/modules/core/plugins/clientAuthRefresh'

/**
 * Adds the current user source token without overriding the authentication
 * required by the request context.
 */
export const prepareUserSourceRequestHeaders = (store) => (config) => {
  const application = store.getters['userSourceUser/getCurrentApplication']
  const isAuthenticated =
    store.getters['userSourceUser/isAuthenticated'](application)

  if (
    !isAuthenticated ||
    store.getters['userSourceUser/isRefreshing'](application)
  ) {
    return config
  }

  config.headers ||= {}
  const token = store.getters['userSourceUser/accessToken'](application)
  const isBaserowUserAuthenticated = store.getters['auth/isAuthenticated']

  if (isBaserowUserAuthenticated && !config.userSourceAuthAsPrimary) {
    config.headers.UserSourceAuthorization = `JWT ${token}`
  } else {
    config.headers.Authorization = `JWT ${token}`
    config.usesUserSourceAuthorization = true
  }

  return config
}

export default defineNuxtPlugin({
  name: 'user-source-client-handler',
  dependsOn: ['client-handler'],
  setup(nuxtApp) {
    const client = nuxtApp.$client
    const store = nuxtApp.$store

    client.interceptors.request.use(prepareUserSourceRequestHeaders(store))

    const shouldInterceptRequest = () => {
      const application = store.getters['userSourceUser/getCurrentApplication']
      return (
        !store.getters['auth/isAuthenticated'] &&
        store.getters['userSourceUser/shouldRefreshToken'](application)
      )
    }

    const shouldInterceptResponse = (error) => {
      const application = store.getters['userSourceUser/getCurrentApplication']
      return (
        !store.getters['auth/isAuthenticated'] &&
        store.getters['userSourceUser/isAuthenticated'](application) &&
        error.response?.data?.error === 'ERROR_INVALID_ACCESS_TOKEN'
      )
    }

    const refreshToken = async () =>
      await store.dispatch('userSourceUser/refreshAuth', {
        application: store.getters['userSourceUser/getCurrentApplication'],
      })

    const refreshAuthInterceptor = makeRefreshAuthInterceptor(
      client,
      refreshToken,
      shouldInterceptRequest,
      shouldInterceptResponse
    )
    client.interceptors.response.use(null, refreshAuthInterceptor)
  },
})
