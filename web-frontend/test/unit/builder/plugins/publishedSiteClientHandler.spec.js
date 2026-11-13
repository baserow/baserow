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
  const { reloadPublishedSite, consumeStaleSiteReloadNotice } =
    await import('@baserow/modules/builder/utils/error')
  return {
    makeStalePublishedSiteInterceptor,
    reloadPublishedSite,
    consumeStaleSiteReloadNotice,
  }
}

let makeStalePublishedSiteInterceptor
let reloadPublishedSite
let consumeStaleSiteReloadNotice

beforeEach(async () => {
  sessionStorage.clear()
  reloadNuxtApp.mockClear()
  const modules = await loadModules()
  makeStalePublishedSiteInterceptor = modules.makeStalePublishedSiteInterceptor
  reloadPublishedSite = modules.reloadPublishedSite
  consumeStaleSiteReloadNotice = modules.consumeStaleSiteReloadNotice
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
  // Only the errors of something the visitor did ask the reloaded page to tell
  // them to try again, as what they typed is lost.
  test.each([
    { code: 'ERROR_PAGE_DOES_NOT_EXIST', notify: false },
    { code: 'ERROR_ELEMENT_DOES_NOT_EXIST', notify: false },
    { code: 'ERROR_DATA_SOURCE_DOES_NOT_EXIST', notify: false },
    { code: 'ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST', notify: true },
    { code: 'ERROR_USER_SOURCE_DOES_NOT_EXIST', notify: true },
  ])('reloads the current route on $code', async ({ code, notify }) => {
    const reload = vi.fn(() => true)
    const interceptor = makeStalePublishedSiteInterceptor(
      makeRouter('application-builder-page'),
      reload
    )

    const result = interceptor(notFound(code))

    expect(reload).toHaveBeenCalledWith('/jobs?id=7', { notify })
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

  test('tells the reloaded document once to show the notice', () => {
    expect(reloadPublishedSite('/jobs', { notify: true })).toBe(true)
    expect(consumeStaleSiteReloadNotice()).toBe(true)
    expect(consumeStaleSiteReloadNotice()).toBe(false)
  })

  test('keeps the notice of a later parallel request', () => {
    expect(reloadPublishedSite('/jobs')).toBe(true)
    expect(reloadPublishedSite('/jobs', { notify: true })).toBe(true)
    expect(reloadNuxtApp).toHaveBeenCalledTimes(1)
    expect(consumeStaleSiteReloadNotice()).toBe(true)
  })

  test('does not show the notice without notify or a reload', async () => {
    expect(reloadPublishedSite('/jobs')).toBe(true)
    expect(consumeStaleSiteReloadNotice()).toBe(false)

    reloadPublishedSite = (await loadModules()).reloadPublishedSite
    expect(reloadPublishedSite('/jobs', { notify: true })).toBe(false)
    expect(consumeStaleSiteReloadNotice()).toBe(false)
  })
})
