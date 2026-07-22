import { createError, showError } from '#imports'

export const BUILDER_PREVIEW_SESSION_INVALID =
  'ERROR_BUILDER_PREVIEW_SESSION_INVALID'

export const createBuilderPreviewSessionError = (i18n) => {
  const error = createError({
    statusCode: 401,
    message: i18n.t('publicPage.previewSessionExpiredTitle'),
    data: {
      report: false,
      error: BUILDER_PREVIEW_SESSION_INVALID,
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

export default defineNuxtPlugin({
  name: 'builder-preview-client-handler',
  dependsOn: ['client-handler'],
  setup(nuxtApp) {
    nuxtApp.$client.interceptors.response.use(
      null,
      makeBuilderPreviewSessionErrorInterceptor(nuxtApp.$i18n, showError)
    )
  },
})
