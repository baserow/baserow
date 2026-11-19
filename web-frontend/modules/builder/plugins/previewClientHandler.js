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
export const prepareBuilderPreviewRequest =
  (previewSsrCookieHeader) => (config) => {
    if (
      config.skipBuilderPreviewRequestHandling ||
      getBuilderPreviewIdFromApiUrl(config.url) === null
    ) {
      return config
    }

    config.withCredentials = true
    config.userSourceAuthAsPrimary = true
    config.headers ||= {}
    if (previewSsrCookieHeader) {
      config.headers.Cookie = previewSsrCookieHeader
    }

    return config
  }

export default defineNuxtPlugin({
  name: 'builder-preview-client-handler',
  dependsOn: ['user-source-client-handler'],
  setup(nuxtApp) {
    const runtimeConfig = useRuntimeConfig()
    const route = useRoute()
    let previewSsrCookieHeader

    if (import.meta.server) {
      const builderId = Number(route.params.builderId)
      if (Number.isInteger(builderId)) {
        const session = useCookie(
          getBuilderPreviewSsrCookieName(runtimeConfig),
          { readonly: true }
        ).value
        if (session) {
          previewSsrCookieHeader = `${getBuilderPreviewCookieName(runtimeConfig)}=${session}`
        }
      }
    }

    nuxtApp.$client.interceptors.request.use(
      prepareBuilderPreviewRequest(previewSsrCookieHeader)
    )
    nuxtApp.$client.interceptors.response.use(
      null,
      makeBuilderPreviewSessionErrorInterceptor(nuxtApp.$i18n, showError)
    )

    if (import.meta.server) {
      // Share the scoped credential with optional reads in the same request.
      return {
        provide: { builderPreviewSsrCookieHeader: previewSsrCookieHeader },
      }
    }
  },
})
