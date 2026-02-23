import { useRuntimeConfig } from '#imports'
import * as Sentry from '@sentry/nuxt'

const config = useRuntimeConfig()
const dsn = config.public.sentryDsn

if (dsn && dsn !== '') {
  Sentry.init({
    dsn,
    release: `baserow-web-frontend@${config.public.version}`,
    environment: config.public.sentryEnvironment || 'production',
    tracesSampleRate: 1.0,
    beforeSend(event, hint) {
      const err = hint?.originalException
      if (err?.fatal === false) return null
      return event
    },
  })
}
