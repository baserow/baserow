// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { nextTick } from 'vue'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'

const env = vi.hoisted(() => ({
  runtimeConfig: null,
  router: null,
  nuxtApp: null,
  sdk: null,
  sdkReady: null,
  sdkRequested: false,
}))

mockNuxtImport('useRuntimeConfig', () => () => env.runtimeConfig)
mockNuxtImport('useRouter', () => () => env.router)
mockNuxtImport('useNuxtApp', () => () => env.nuxtApp)

function deferred() {
  let resolve, reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('lazy PostHog initialization', () => {
  let sdkReady

  beforeEach(() => {
    vi.resetModules()
    sdkReady = deferred()
    env.sdkReady = sdkReady.promise
    env.sdkRequested = false
    env.runtimeConfig = {
      public: {
        posthogProjectApiKey: 'project-key',
        posthogHost: '/analytics',
      },
    }
    env.router = {
      afterEach: vi.fn(),
      isReady: vi.fn().mockResolvedValue(),
      currentRoute: { value: { fullPath: '/login?next=workspace', meta: {} } },
    }
    env.nuxtApp = {
      provide: vi.fn(),
      $store: {
        getters: {
          'auth/isAuthenticated': false,
          'auth/getUserId': null,
          'auth/getUsername': null,
        },
      },
    }
    env.sdk = {
      init: vi.fn(),
      capture: vi.fn(),
      identify: vi.fn(),
      get_distinct_id: vi.fn().mockReturnValue('anonymous'),
    }
    vi.doMock('posthog-js', async () => {
      env.sdkRequested = true
      await env.sdkReady
      return { default: env.sdk }
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  async function start() {
    const { default: plugin } =
      await import('@baserow/modules/core/plugins/posthog')
    return plugin()
  }

  async function loadSDK() {
    sdkReady.resolve()
    await vi.dynamicImportSettled()
    await nextTick()
  }

  test('does not wait for the SDK and captures the route already loaded at startup', async () => {
    expect(await start()).toBeUndefined()
    expect(env.sdk.init).not.toHaveBeenCalled()

    await loadSDK()

    expect(env.nuxtApp.provide).toHaveBeenCalledWith('posthog', env.sdk)
    expect(env.sdk.capture).toHaveBeenCalledExactlyOnceWith('$pageview', {
      $current_url: `${window.location.origin}/login?next=workspace`,
    })
  })

  test('captures initial navigation once when the SDK loads before the router is ready', async () => {
    const routerReady = deferred()
    env.router.isReady.mockReturnValue(routerReady.promise)
    await start()
    await loadSDK()
    expect(env.sdk.capture).not.toHaveBeenCalled()

    const to = { fullPath: '/workspace/1', meta: {} }
    env.router.currentRoute.value = to
    env.router.afterEach.mock.calls[0][0](to, {}, undefined)
    routerReady.resolve()
    await nextTick()
    await nextTick()

    expect(env.sdk.capture).toHaveBeenCalledExactlyOnceWith('$pageview', {
      $current_url: `${window.location.origin}/workspace/1`,
    })
  })

  test('identifies the user and respects tracking prevention on the startup route', async () => {
    env.nuxtApp.$store.getters = {
      'auth/isAuthenticated': true,
      'auth/getUserId': 42,
      'auth/getUsername': 'user@example.com',
    }
    env.router.currentRoute.value.meta.preventPageViewTracking = true
    await start()
    await loadSDK()

    expect(env.sdk.identify).toHaveBeenCalledWith(42, {
      user_email: 'user@example.com',
    })
    expect(env.sdk.capture).not.toHaveBeenCalled()
  })

  test('tracks later successful navigation while ignoring failed navigation', async () => {
    await start()
    await loadSDK()
    env.sdk.capture.mockClear()
    const afterEach = env.router.afterEach.mock.calls[0][0]

    afterEach({ fullPath: '/cancelled', meta: {} }, {}, new Error('cancelled'))
    afterEach({ fullPath: '/workspace/2', meta: {} }, {}, undefined)
    await nextTick()

    expect(env.sdk.capture).toHaveBeenCalledExactlyOnceWith('$pageview', {
      $current_url: `${window.location.origin}/workspace/2`,
    })
  })

  test('skips SDK initialization on an unconfigured installation', async () => {
    env.runtimeConfig.public = {
      posthogProjectApiKey: '',
      posthogHost: '',
    }
    await start()
    sdkReady.resolve()
    await vi.dynamicImportSettled()

    expect(env.sdk.init).not.toHaveBeenCalled()
    expect(env.router.afterEach).not.toHaveBeenCalled()
  })

  test('handles a rejected SDK chunk without failing startup', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const error = new Error('chunk unavailable')
    await start()
    await vi.waitFor(() => expect(env.sdkRequested).toBe(true))
    sdkReady.reject(error)
    await vi.dynamicImportSettled()

    expect(warning).toHaveBeenCalledWith(
      'Failed to initialize PostHog:',
      expect.any(Error)
    )
    expect(env.nuxtApp.provide).not.toHaveBeenCalled()
  })

  test('handles SDK initialization errors without failing startup', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const error = new Error('SDK initialization failed')
    env.sdk.init.mockImplementation(() => {
      throw error
    })
    await start()
    await loadSDK()

    expect(warning).toHaveBeenCalledWith('Failed to initialize PostHog:', error)
    expect(env.nuxtApp.provide).not.toHaveBeenCalled()
  })
})
