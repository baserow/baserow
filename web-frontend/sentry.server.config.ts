import { useRuntimeConfig } from '#imports'
import * as Sentry from '@sentry/nuxt'
import { makeFakeTransport } from './modules/core/utils/sentryFakeTransport'
import { SILENCED_API_ERRORS } from './modules/core/utils/sentryErrors'

const config = useRuntimeConfig()
const dsn =
  config.public.sentryDsn === 'fake'
    ? 'https://fake@localhost/1'
    : config.public.sentryDsn
const isDev = import.meta.dev && config.public.sentryDsn === 'fake'

if (dsn && dsn !== '') {
  Sentry.init({
    dsn,
    release: `baserow-web-frontend@${config.public.version}`,
    environment: config.public.sentryEnvironment || 'production',
    tracesSampleRate: 1.0,
    ...(isDev ? { transport: makeFakeTransport } : {}),
    beforeSend(event, hint) {
      const err = hint?.originalException
      if (err?.fatal === false) return null

      // Filter known API errors that are handled by the application (e.g. forceLogoff).
      const status = err?.response?.status || err?.statusCode
      const errorCode = err?.response?.data?.error || err?.data?.error
      if (SILENCED_API_ERRORS[status]?.includes(errorCode)) {
        return null
      }
      if (isDev) {
        console.error('[Sentry captured error]', err)
        return null
      } else {
        return event
      }
    },
  })
}
