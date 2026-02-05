function isValidHttpUrl(rawString) {
  try {
    const url = new URL(rawString)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch (_) {
    return false
  }
}

/**
 * This middleware validates that URL environment variables are properly configured.
 */
export default defineNuxtRouteMiddleware(() => {
  const event = import.meta.server ? useRequestEvent() : null
  const nuxtApp = useNuxtApp()
  const config = useRuntimeConfig()
  const i18n = nuxtApp.$i18n
  const translate = (key, params) =>
    i18n && typeof i18n.t === 'function' ? i18n.t(key, params) : key

  // If nuxt generate, pass this middleware
  if (import.meta.server && !event) return

  if (import.meta.server && !config.public.baserowDisablePublicUrlCheck) {
    // Validate configured URLs
    const urlsToCheck = {
      publicBackendUrl: config.public.publicBackendUrl,
      publicWebFrontendUrl: config.public.publicWebFrontendUrl,
    }

    for (const [name, value] of Object.entries(urlsToCheck)) {
      if (value && !isValidHttpUrl(value)) {
        throw createError({
          statusCode: 500,
          hideBackButton: true,
          message: translate('urlCheck.invalidUrlEnvVarTitle', { name }),
          content: translate('urlCheck.invalidUrlEnvVarDescription', { name }),
        })
      }
    }
  }
})
