// @vitest-environment node
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'

const env = vi.hoisted(() => ({
  runtimeConfig: null,
  appConfig: null,
  router: {},
  init: vi.fn(),
  tracing: vi.fn(() => ({ name: 'BrowserTracing' })),
  replay: vi.fn(() => ({ name: 'Replay' })),
}))

mockNuxtImport('useRuntimeConfig', () => () => env.runtimeConfig)
mockNuxtImport('useAppConfig', () => () => env.appConfig)
mockNuxtImport('useRouter', () => () => env.router)

vi.mock('@sentry/nuxt', () => ({
  init: env.init,
  browserTracingIntegration: env.tracing,
  replayIntegration: env.replay,
}))

describe('Sentry client sampling configuration', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    env.runtimeConfig = {
      public: {
        sentryDsn: 'https://key@sentry.example.com/1',
        sentryTracesSampleRate: '0',
        sentryReplaysOnErrorSampleRate: '0',
        sentryEnvironment: 'production',
        version: '2.4.0',
      },
    }
    env.appConfig = {}
  })

  async function initialize() {
    await import('@baserow/sentry.client.config')
    return env.init.mock.calls[0]?.[0]
  }

  test('does not initialize Sentry without a DSN', async () => {
    env.runtimeConfig.public.sentryDsn = ''
    await initialize()

    expect(env.init).not.toHaveBeenCalled()
    expect(env.tracing).not.toHaveBeenCalled()
    expect(env.replay).not.toHaveBeenCalled()
  })

  test('keeps error reporting while omitting explicit tracing and replay at zero sample rates', async () => {
    const config = await initialize()

    expect(config.integrations).toEqual([])
    expect(config.beforeSend({ message: 'unexpected error' }, {})).toEqual({
      message: 'unexpected error',
    })
    expect(
      config.beforeSend(
        {},
        { originalException: { name: 'AxiosError', response: undefined } }
      )
    ).toBeNull()
    expect(config.ignoreErrors).not.toHaveLength(0)
  })

  test('uses runtime sampling rates when no app-config override exists', async () => {
    env.runtimeConfig.public.sentryTracesSampleRate = '0.25'
    env.runtimeConfig.public.sentryReplaysOnErrorSampleRate = '0.5'
    const config = await initialize()

    expect(config.tracesSampleRate).toBe(0.25)
    expect(config.replaysOnErrorSampleRate).toBe(0.5)
    expect(config.integrations).toEqual([
      { name: 'BrowserTracing' },
      { name: 'Replay' },
    ])
    expect(env.tracing).toHaveBeenCalledWith({ router: env.router })
    expect(env.replay).toHaveBeenCalledWith({
      maskAllText: true,
      blockAllMedia: true,
    })
  })

  test('enables integrations for positive app-config sampling overrides', async () => {
    env.appConfig = {
      sentry: {
        config: { tracesSampleRate: 0.5, replaysOnErrorSampleRate: 1 },
      },
    }
    const config = await initialize()

    expect(config.integrations).toEqual([
      { name: 'BrowserTracing' },
      { name: 'Replay' },
    ])
  })

  test('omits integrations when app config overrides positive runtime rates to zero', async () => {
    env.runtimeConfig.public.sentryTracesSampleRate = '1'
    env.runtimeConfig.public.sentryReplaysOnErrorSampleRate = '1'
    env.appConfig = {
      sentry: { config: { tracesSampleRate: 0, replaysOnErrorSampleRate: 0 } },
    }
    const config = await initialize()

    expect(config.integrations).toEqual([])
    expect(env.tracing).not.toHaveBeenCalled()
    expect(env.replay).not.toHaveBeenCalled()
  })

  test('enables replay for session sampling configured through app config', async () => {
    env.appConfig = { sentry: { config: { replaysSessionSampleRate: 0.5 } } }
    const config = await initialize()

    expect(config.integrations).toEqual([{ name: 'Replay' }])
  })

  test('enables tracing when a custom sampler determines the sample rate', async () => {
    const tracesSampler = () => 0.5
    env.appConfig = { sentry: { config: { tracesSampler } } }
    const config = await initialize()

    expect(config.tracesSampler).toBe(tracesSampler)
    expect(config.integrations).toEqual([{ name: 'BrowserTracing' }])
  })

  test('appends custom integrations without mutating app config', async () => {
    const customIntegrations = [{ name: 'CustomIntegration' }]
    const userConfig = Object.freeze({
      replaysOnErrorSampleRate: 1,
      integrations: customIntegrations,
    })
    env.appConfig = { sentry: { config: userConfig } }
    const config = await initialize()

    expect(config.integrations).toEqual([
      { name: 'Replay' },
      { name: 'CustomIntegration' },
    ])
    expect(userConfig.integrations).toBe(customIntegrations)
  })
})
