import {
  createError,
  showError,
  useCookie,
  useRoute,
  useRuntimeConfig,
} from '#imports'

import {
  getBuilderPreviewCookieName,
  getBuilderPreviewIdFromApiUrl,
  getBuilderPreviewSsrCookieName,
} from '@baserow/modules/builder/utils/preview'

export const BUILDER_PREVIEW_SESSION_INVALID =
  'ERROR_BUILDER_PREVIEW_SESSION_INVALID'

export const createBuilderPreviewSessionError = (i18n) => {
  const error = createError({
    statusCode: 401,
    message: i18n.t('publicPage.previewSessionExpiredTitle'),
    data: {
      report: false,
      error: BUILDER_PREVIEW_SESSION_INVALID,
      closeTab: true,
    },
    fatal: true,
  })
  error.content = i18n.t('publicPage.previewSessionExpiredDescription')
  return error
}

export const makeBuilderPreviewSessionErrorInterceptor = (
  i18n,
  nuxtErrorHandler
) => {
  return (error) => {
    if (error.response?.data?.error === BUILDER_PREVIEW_SESSION_INVALID) {
      const previewSessionError = createBuilderPreviewSessionError(i18n)
      nuxtErrorHandler(previewSessionError)
      return Promise.reject(previewSessionError)
    }

    return Promise.reject(error)
  }
}

/**
 * Sends browser or SSR preview-session credentials only to preview API URLs.
 */
export const prepareBuilderPreviewRequest = (previewSsrAuth) => (config) => {
  if (getBuilderPreviewIdFromApiUrl(config.url) === null) {
    return config
  }

  config.withCredentials = true
  config.userSourceAuthAsPrimary = true
  config.headers ||= {}
  if (previewSsrAuth.session) {
    config.headers.Cookie = `${previewSsrAuth.backendCookieName}=${previewSsrAuth.session}`
  }

  return config
}

export default defineNuxtPlugin({
  name: 'builder-preview-client-handler',
  dependsOn: ['user-source-client-handler'],
  setup(nuxtApp) {
    const runtimeConfig = useRuntimeConfig()
    const route = useRoute()
    const previewSsrAuth = {}

    if (import.meta.server) {
      const builderId = Number(route.params.builderId)
      if (Number.isInteger(builderId)) {
        previewSsrAuth.session = useCookie(
          getBuilderPreviewSsrCookieName(runtimeConfig)
        ).value
        previewSsrAuth.backendCookieName =
          getBuilderPreviewCookieName(runtimeConfig)
      }
    }

    nuxtApp.$client.interceptors.request.use(
      prepareBuilderPreviewRequest(previewSsrAuth)
    )
    nuxtApp.$client.interceptors.response.use(
      null,
      makeBuilderPreviewSessionErrorInterceptor(nuxtApp.$i18n, showError)
    )
  },
})
