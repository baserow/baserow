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
export const prepareBuilderPreviewRequest = (ssrCookie) => (config) => {
  if (
    config.skipBuilderPreviewRequestHandling ||
    getBuilderPreviewIdFromApiUrl(config.url) === null
  ) {
    return config
  }

  config.withCredentials = true
  config.userSourceAuthAsPrimary = true
  config.headers ||= {}
  if (ssrCookie) {
    config.headers.Cookie = ssrCookie
  }

  return config
}

export default defineNuxtPlugin({
  name: 'builder-preview-client-handler',
  dependsOn: ['user-source-client-handler'],
  setup(nuxtApp) {
    const runtimeConfig = useRuntimeConfig()
    const route = useRoute()
    const session =
      import.meta.server && Number.isInteger(Number(route.params.builderId))
        ? useCookie(getBuilderPreviewSsrCookieName(runtimeConfig), {
            readonly: true,
          }).value
        : null
    const ssrCookie = session
      ? `${getBuilderPreviewCookieName(runtimeConfig)}=${session}`
      : null

    nuxtApp.$client.interceptors.request.use(
      prepareBuilderPreviewRequest(ssrCookie)
    )
    nuxtApp.$client.interceptors.response.use(
      null,
      makeBuilderPreviewSessionErrorInterceptor(nuxtApp.$i18n, showError)
    )

    if (ssrCookie) {
      // Share the scoped credential with optional reads in the same request.
      return { provide: { builderPreviewSsrCookieHeader: ssrCookie } }
    }
  },
})
