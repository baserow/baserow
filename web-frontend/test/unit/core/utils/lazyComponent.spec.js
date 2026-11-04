import { beforeEach, describe, expect, test, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { withLoadingIndicator } from '@baserow/modules/core/utils/lazyComponent'

const state = vi.hoisted(() => ({
  app: undefined,
  fallback: { start: vi.fn(), finish: vi.fn() },
}))

mockNuxtImport(
  'tryUseNuxtApp',
  (original) => () => (state.app === undefined ? original() : state.app)
)
mockNuxtImport(
  'useLoadingIndicator',
  (original) =>
    (...args) =>
      state.app === undefined
        ? original(...args)
        : state.app?.indicator || state.fallback
)

/** Control completion order without timing or network dependencies. */
function deferred() {
  let resolve
  let reject
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
}

function createApp() {
  return {
    isHydrating: false,
    runWithContext: (callback) => callback(),
    indicator: { start: vi.fn(), finish: vi.fn() },
  }
}

describe('feature bundle loading indicator', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.app = createApp()
  })

  test('keeps the bar active until concurrent loads finish, including failures', async () => {
    const { indicator } = state.app
    const first = deferred()
    const second = deferred()
    const firstLoad = withLoadingIndicator(() => first.promise)
    const secondLoad = withLoadingIndicator(() => second.promise)
    const chunkError = new Error('Chunk unavailable')
    const failure = firstLoad.catch((error) => error)

    expect(indicator.start).toHaveBeenCalledTimes(1)
    first.reject(chunkError)
    await expect(failure).resolves.toBe(chunkError)
    expect(indicator.finish).not.toHaveBeenCalled()

    second.resolve('loaded')
    await expect(secondLoad).resolves.toBe('loaded')
    expect(indicator.finish).toHaveBeenCalledTimes(1)
  })

  test('clears a synchronous failure and starts tracking a subsequent load', async () => {
    const { indicator } = state.app
    await expect(
      withLoadingIndicator(() => {
        throw new Error('Loader failed')
      })
    ).rejects.toThrow('Loader failed')
    expect(indicator.finish).toHaveBeenCalledTimes(1)

    const next = deferred()
    const load = withLoadingIndicator(() => next.promise)
    expect(indicator.start).toHaveBeenCalledTimes(2)
    expect(indicator.finish).toHaveBeenCalledTimes(1)
    next.resolve('retried')
    await expect(load).resolves.toBe('retried')
    expect(indicator.finish).toHaveBeenCalledTimes(2)
  })

  test('tracks separate app instances independently', async () => {
    const firstApp = state.app
    const first = deferred()
    const firstLoad = withLoadingIndicator(() => first.promise)
    state.app = createApp()
    const secondApp = state.app
    const second = deferred()
    const secondLoad = withLoadingIndicator(() => second.promise)

    expect(firstApp.indicator.start).toHaveBeenCalledTimes(1)
    expect(secondApp.indicator.start).toHaveBeenCalledTimes(1)
    first.resolve('first')
    await firstLoad
    expect(firstApp.indicator.finish).toHaveBeenCalledTimes(1)
    expect(secondApp.indicator.finish).not.toHaveBeenCalled()
    second.resolve('second')
    await secondLoad
    expect(secondApp.indicator.finish).toHaveBeenCalledTimes(1)
  })

  test('does not initialize or start an indicator during initial hydration', async () => {
    const { indicator } = state.app
    state.app.isHydrating = true
    state.app.runWithContext = vi.fn()
    await expect(
      withLoadingIndicator(() => Promise.resolve('hydrated'))
    ).resolves.toBe('hydrated')
    expect(state.app.runWithContext).not.toHaveBeenCalled()
    expect(indicator.start).not.toHaveBeenCalled()
    expect(indicator.finish).not.toHaveBeenCalled()
  })

  test('still executes loaders without an active Nuxt context', async () => {
    state.app = null
    await expect(
      withLoadingIndicator(() => Promise.resolve('loaded'))
    ).resolves.toBe('loaded')
    expect(state.fallback.start).not.toHaveBeenCalled()
    expect(state.fallback.finish).not.toHaveBeenCalled()
  })
})
