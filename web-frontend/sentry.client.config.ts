import { useRuntimeConfig, useAppConfig, useRouter } from '#imports'
import { makeFakeTransport } from './modules/core/utils/sentryFakeTransport'
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
