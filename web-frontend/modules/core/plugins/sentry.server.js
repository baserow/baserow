export default defineNuxtPlugin(async (nuxtApp) => {
  if (import.meta.client) {
    return
  }

  const config = useRuntimeConfig()
  const dsn = config.public.sentryDsn

  if (!dsn || dsn === '') {
    return
  }

  const Sentry = await import('@sentry/node')

  Sentry.init({
    dsn,
    environment: config.public.sentryEnvironment || 'production',
    tracesSampleRate: 1.0,
  })

  nuxtApp.hook('app:error', (error) => {
    Sentry.captureException(error)
  })

  nuxtApp.hook('vue:error', (error, instance, info) => {
    Sentry.captureException(error, {
      contexts: {
        vue: {
          componentName: instance?.$options?.name,
          errorInfo: info,
        },
      },
    })
  })
})
