function isValidHttpUrl(rawString) {
  try {
    const url = new URL(rawString)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch (_) {
    return false
  }
}

function invalidUrlEnvVariable(envVariableName) {
  /**
   * This function lets us check on startup that a provided environment variable is
   * a valid url. If we didn't do this then whenever the user would try to send a
   * HTTP request they would get a mysterious 500 error raised by the http client.
   *
   * @type {string}
   */

  const envValue = process.env[envVariableName]
  return envValue && !isValidHttpUrl(envValue)
}
/**
 * This middleware makes sure that the current user is admin else a 403 error
 * will be shown to the user.
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
    const urlEnvVarsToCheck = []
    if (process.env.BASEROW_PUBLIC_URL) {
      urlEnvVarsToCheck.push('BASEROW_PUBLIC_URL')
    } else {
      urlEnvVarsToCheck.push('PUBLIC_BACKEND_URL', 'PUBLIC_WEB_FRONTEND_URL')
    }

    for (const name of urlEnvVarsToCheck) {
      if (invalidUrlEnvVariable(name)) {
        // noinspection HttpUrlsUsage
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

/*
Previous Nuxt 2 middleware:
export default function ({ store, req, error, i18n }) {
  // If nuxt generate, pass this middleware
  if (import.meta.server && !req) return

  if (import.meta.server && !process.env.BASEROW_DISABLE_PUBLIC_URL_CHECK) {
    const urlEnvVarsToCheck = []
    if (process.env.BASEROW_PUBLIC_URL) {
      urlEnvVarsToCheck.push('BASEROW_PUBLIC_URL')
    } else {
      urlEnvVarsToCheck.push('PUBLIC_BACKEND_URL', 'PUBLIC_WEB_FRONTEND_URL')
    }

    for (const name of urlEnvVarsToCheck) {
      if (invalidUrlEnvVariable(name)) {
        // noinspection HttpUrlsUsage
        return error({
          statusCode: 500,
          hideBackButton: true,
          message: i18n.t('urlCheck.invalidUrlEnvVarTitle', { name }),
          content: i18n.t('urlCheck.invalidUrlEnvVarDescription', { name }),
        })
      }
    }
  }
}
*/
