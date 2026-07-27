import { FF_AI_PROVIDERS } from '@baserow/modules/core/plugins/featureFlags'

export default defineNuxtRouteMiddleware(() => {
  const nuxtApp = useNuxtApp()
  if (!nuxtApp.$featureFlagIsEnabled(FF_AI_PROVIDERS)) {
    return abortNavigation(
      createError({
        statusCode: 404,
        message: nuxtApp.$i18n.t('errorLayout.pageNotFoundTitle'),
        data: { report: false },
        fatal: true,
      })
    )
  }
})
