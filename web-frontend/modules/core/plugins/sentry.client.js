export default defineNuxtPlugin(async (nuxtApp) => {
  // Only run on client side
  if (import.meta.server) {
    return
  }

  const config = useRuntimeConfig()
  const dsn = config.public.sentryDsn

  if (!dsn || dsn === '') {
    return
  }

  const Sentry = await import('@sentry/vue')

  Sentry.init({
    app: nuxtApp.vueApp,
    dsn,
    environment: config.public.sentryEnvironment || 'production',
    integrations: [
      Sentry.browserTracingIntegration({
        router: nuxtApp.$router,
      }),
      Sentry.replayIntegration({
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],
    tracesSampleRate: 1.0,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 1.0,
  })
})
