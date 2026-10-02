import { useRuntimeConfig, useAppConfig, useRouter } from '#imports'
import { makeFakeTransport } from './modules/core/utils/sentryFakeTransport'
import {
  SILENCED_API_ERRORS,
  SILENCED_ERROR_PATTERNS,
} from './modules/core/utils/sentryErrors'
import * as Sentry from '@sentry/nuxt'

const config = useRuntimeConfig()
const appConfig = useAppConfig()
const dsn =
  config.public.sentryDsn === 'fake'
    ? 'https://fake@localhost/1'
    : config.public.sentryDsn
const isDev = import.meta.dev && config.public.sentryDsn === 'fake'

if (dsn && dsn !== '') {
  const tracesSampleRate = parseFloat(config.public.sentryTracesSampleRate) || 0
  const replaysOnErrorSampleRate =
    parseFloat(config.public.sentryReplaysOnErrorSampleRate) || 0

  const defaultConfig = {
    dsn,
    release: `baserow-web-frontend@${config.public.version}`,
    environment: config.public.sentryEnvironment || 'production',
    ignoreErrors: SILENCED_ERROR_PATTERNS,
    tracesSampleRate,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate,
    ...(isDev ? { transport: makeFakeTransport } : {}),
    beforeSend(event, hint) {
      const err = hint?.originalException
      if (err?.fatal === false) {
        return null
      } else if (err?.fatal === true && err?.data?.report === false) {
        return null
      }
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
  const finalConfig = {
    ...defaultConfig,
    ...userConfig,
  }

  // Decide after overrides so custom sampling still has the integrations it
  // needs. Replay buffers sessions even at sample rate 0; skip it when neither
  // session sampling nor on-error sampling can save a replay.
  const integrations = []
  if (
    finalConfig.tracesSampleRate > 0 ||
    typeof finalConfig.tracesSampler === 'function'
  ) {
    integrations.push(
      Sentry.browserTracingIntegration({
        router: useRouter(),
      })
    )
  }
  if (
    finalConfig.replaysSessionSampleRate > 0 ||
    finalConfig.replaysOnErrorSampleRate > 0
  ) {
    integrations.push(
      Sentry.replayIntegration({
        maskAllText: true,
        blockAllMedia: true,
      })
    )
  }
  finalConfig.integrations = [
    ...integrations,
    ...(userConfig.integrations || []),
  ]

  Sentry.init(finalConfig)
}
