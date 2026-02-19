import { useRuntimeConfig, useAppConfig, useRouter } from '#imports'
import * as Sentry from '@sentry/nuxt'

const config = useRuntimeConfig()
const appConfig = useAppConfig()
const dsn = config.public.sentryDsn

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
