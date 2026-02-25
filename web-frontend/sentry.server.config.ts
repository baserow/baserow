import { useRuntimeConfig } from '#imports'
import * as Sentry from '@sentry/nuxt'
import { makeFakeTransport } from './modules/core/utils/sentryFakeTransport'

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
      if (isDev) {
        console.error('[Sentry captured error]', err)
        return null
      } else {
        return event
      }
    },
  })
}
