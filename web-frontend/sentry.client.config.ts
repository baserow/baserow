import { useRuntimeConfig, useAppConfig, useRouter } from '#imports'
import { makeFakeTransport } from './modules/core/utils/sentryFakeTransport'
import { SILENCED_API_ERRORS } from './modules/core/utils/sentryErrors'
import * as Sentry from '@sentry/nuxt'

const config = useRuntimeConfig()
const appConfig = useAppConfig()
const dsn =
  config.public.sentryDsn === 'fake'
    ? 'https://fake@localhost/1'
    : config.public.sentryDsn
const isDev = import.meta.dev && config.public.sentryDsn === 'fake'

if (dsn && dsn !== '') {
  const defaultConfig = {
    dsn,
    release: `baserow-web-frontend@${config.public.version}`,
    environment: config.public.sentryEnvironment || 'production',
    integrations: [
      Sentry.browserTracingIntegration({
        router: useRouter(),
      }),
      Sentry.replayIntegration({
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],
    tracesSampleRate: 1.0,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 1.0,
    ...(isDev ? { transport: makeFakeTransport } : {}),
    beforeSend(event, hint) {
      const err = hint?.originalException
      if (err?.fatal === false) return null

      // Filter out axios errors without a response like
      // network error, timeout, aborted, cancelled requests
      if (err?.name === 'AxiosError' && !err?.response) {
        return null
      }

      // Filter known API errors that are handled by the application (e.g. forceLogoff).
      const status = err?.response?.status || err?.statusCode
      const errorCode = err?.response?.data?.error || err?.data?.error
      if (SILENCED_API_ERRORS[status]?.includes(errorCode)) {
        return null
      }

      if (isDev) {
        console.error('[Sentry captured error]', `${err}`)
        return null
      } else {
        return event
      }
    },
  }

  // Merge with user-provided configuration from app config
  // appConfig.sentry.config can be used to extend or override defaults
  const userConfig = appConfig.sentry?.config || {}
  let finalIntegrations = defaultConfig.integrations
  if (userConfig.integrations) {
    finalIntegrations = [
      ...defaultConfig.integrations,
      ...userConfig.integrations,
    ]
    delete userConfig.integrations
  }

  const finalConfig = {
    ...defaultConfig,
    ...userConfig,
    integrations: finalIntegrations,
  }

  Sentry.init(finalConfig)
}
