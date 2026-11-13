import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

const reloadNuxtApp = vi.hoisted(() => vi.fn())

vi.mock('#app', async (importOriginal) => ({
  ...(await importOriginal()),
  reloadNuxtApp,
}))

// Imports the modules again, like a newly loaded document does, so the reload
// started by a previous test or document is forgotten.
const loadModules = async () => {
  vi.resetModules()
  const { makeStalePublishedSiteInterceptor } =
    await import('@baserow/modules/builder/plugins/publishedSiteClientHandler')
  const { reloadPublishedSite } =
    await import('@baserow/modules/builder/utils/error')
  return { makeStalePublishedSiteInterceptor, reloadPublishedSite }
}

let makeStalePublishedSiteInterceptor
let reloadPublishedSite

beforeEach(async () => {
  sessionStorage.clear()
  reloadNuxtApp.mockClear()
  const modules = await loadModules()
  makeStalePublishedSiteInterceptor = modules.makeStalePublishedSiteInterceptor
  reloadPublishedSite = modules.reloadPublishedSite
})

const notFound = (error) => ({
  response: { status: 404, data: { error } },
})

const makeRouter = (name, fullPath = '/jobs?id=7') => ({
  currentRoute: { value: { name, fullPath } },
})

// Resolves to 'pending' when the promise hasn't settled after the current tick.
const settledState = (promise) =>
  Promise.race([
    promise.then(
      () => 'resolved',
      () => 'rejected'
    ),
    new Promise((resolve) => setTimeout(() => resolve('pending'), 0)),
  ])

describe('stale published site interceptor', () => {
  test.each([
    'ERROR_PAGE_DOES_NOT_EXIST',
    'ERROR_ELEMENT_DOES_NOT_EXIST',
    'ERROR_DATA_SOURCE_DOES_NOT_EXIST',
    'ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST',
    'ERROR_USER_SOURCE_DOES_NOT_EXIST',
  ])('reloads the current route on %s', async (code) => {
    const reload = vi.fn(() => true)
    const interceptor = makeStalePublishedSiteInterceptor(
      makeRouter('application-builder-page'),
      reload
    )

    const result = interceptor(notFound(code))

    expect(reload).toHaveBeenCalledWith('/jobs?id=7')
    expect(await settledState(result)).toBe('pending')
  })

  test.each([
    {
      name: 'a missing row',
      routeName: 'application-builder-page',
      error: notFound('ERROR_DATA_DOES_NOT_EXIST'),
    },
    {
      name: 'another status',
      routeName: 'application-builder-page',
      error: {
        response: { status: 400, data: { error: 'ERROR_PAGE_DOES_NOT_EXIST' } },
      },
    },
    {
      name: 'a network error',
      routeName: 'application-builder-page',
      error: {},
    },
    {
      name: 'the editor',
      routeName: 'builder-page',
      error: notFound('ERROR_DATA_SOURCE_DOES_NOT_EXIST'),
    },
  ])('rejects without reloading for $name', async ({ routeName, error }) => {
    const reload = vi.fn(() => true)
    const interceptor = makeStalePublishedSiteInterceptor(
      makeRouter(routeName),
      reload
    )

    await expect(interceptor(error)).rejects.toBe(error)
    expect(reload).not.toHaveBeenCalled()
  })

  test('rejects when the reload is skipped', async () => {
    const error = notFound('ERROR_DATA_SOURCE_DOES_NOT_EXIST')
    const interceptor = makeStalePublishedSiteInterceptor(
      makeRouter('application-builder-preview'),
      () => false
    )

    await expect(interceptor(error)).rejects.toBe(error)
  })

  // A stale tab sends several requests at once with the same stale ids, e.g. the
  // three `fetchPublished` calls of `publicPage.vue`. If any of them rejected,
  // `Promise.all` would show the "page not found" error until the reload is done.
  test('keeps parallel stale requests pending during the reload', async () => {
    const interceptor = makeStalePublishedSiteInterceptor(
      makeRouter('application-builder-page'),
      reloadPublishedSite
    )

    const results = [
      interceptor(notFound('ERROR_PAGE_DOES_NOT_EXIST')),
      interceptor(notFound('ERROR_PAGE_DOES_NOT_EXIST')),
      interceptor(notFound('ERROR_PAGE_DOES_NOT_EXIST')),
    ]

    expect(await Promise.all(results.map(settledState))).toEqual([
      'pending',
      'pending',
      'pending',
    ])
    expect(reloadNuxtApp).toHaveBeenCalledTimes(1)
  })
})

describe('reloadPublishedSite', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  test('drops the hash from the reloaded path', () => {
    expect(reloadPublishedSite('/jobs?id=7#apply')).toBe(true)
    expect(reloadNuxtApp).toHaveBeenCalledWith({
      path: '/jobs?id=7',
      force: true,
    })
  })

  test('reloads only once per document', () => {
    expect(reloadPublishedSite('/jobs')).toBe(true)
    expect(reloadPublishedSite('/jobs')).toBe(true)
    expect(reloadNuxtApp).toHaveBeenCalledTimes(1)
  })

  test('skips a reloaded document within the guard window', async () => {
    expect(reloadPublishedSite('/jobs')).toBe(true)

    vi.advanceTimersByTime(5000)
    reloadPublishedSite = (await loadModules()).reloadPublishedSite
    expect(reloadPublishedSite('/jobs')).toBe(false)
    expect(reloadNuxtApp).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(5001)
    reloadPublishedSite = (await loadModules()).reloadPublishedSite
    expect(reloadPublishedSite('/jobs')).toBe(true)
    expect(reloadNuxtApp).toHaveBeenCalledTimes(2)
  })
})
