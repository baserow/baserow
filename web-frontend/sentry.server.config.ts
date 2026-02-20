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
    beforeSend(event) {
      // Don't report 404 errors
      const statusCode =
        event.contexts?.response?.status_code ??
        (event.exception?.values?.[0]?.value?.includes('404') ? 404 : null)
      if (statusCode === 404) return null
      return event
    },
  })
}
