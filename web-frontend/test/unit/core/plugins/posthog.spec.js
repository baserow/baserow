import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { useNuxtApp, useRouter, useRuntimeConfig } from '#imports'

import plugin from '@baserow/modules/core/plugins/posthog'
import {
  getPosthogOptions,
  getPublishedPageViewProperties,
} from '@baserow/modules/core/utils/publishedSite'

const { posthog } = vi.hoisted(() => ({
  posthog: { init: vi.fn(), capture: vi.fn(), identify: vi.fn() },
}))

vi.mock('posthog-js', () => ({ default: posthog }))

const HOST = 'https://eu.posthog.com'
const CONFIG_KEYS = [
  'posthogProjectApiKey',
  'posthogHost',
  'publicWebFrontendUrl',
  'builderPreviewUrl',
]

describe('posthog plugin', () => {
  let config, original, provide, routerAfterEach

  beforeEach(() => {
    vi.clearAllMocks()
    config = useRuntimeConfig().public
    original = Object.fromEntries(CONFIG_KEYS.map((key) => [key, config[key]]))
    provide = vi.spyOn(useNuxtApp(), 'provide').mockImplementation(() => {})
    routerAfterEach = vi
      .spyOn(useRouter(), 'afterEach')
      .mockImplementation(() => {})
  })

  afterEach(() => {
    Object.assign(config, original)
    vi.restoreAllMocks()
  })

  test('does nothing when PostHog is not configured', async () => {
    Object.assign(config, { posthogProjectApiKey: '', posthogHost: '' })

    await plugin.setup()

    expect(posthog.init).not.toHaveBeenCalled()
    expect(provide).not.toHaveBeenCalled()
  })

  test('provides PostHog and tracks the routes on Baserow itself', async () => {
    Object.assign(config, {
      posthogProjectApiKey: 'phc_test',
      posthogHost: HOST,
      publicWebFrontendUrl: window.location.origin,
    })

    await plugin.setup()

    expect(posthog.init).toHaveBeenCalledWith(
      'phc_test',
      getPosthogOptions({ host: HOST, publishedSite: false })
    )
    expect(provide.mock.calls).toStrictEqual([['posthog', posthog]])
    expect(routerAfterEach).toHaveBeenCalledOnce()
  })

  test('keeps the preview of the editor like Baserow itself', async () => {
    Object.assign(config, {
      posthogProjectApiKey: 'phc_test',
      posthogHost: HOST,
      publicWebFrontendUrl: 'https://baserow.example',
      builderPreviewUrl: window.location.origin,
    })

    await plugin.setup()

    expect(provide.mock.calls).toStrictEqual([['posthog', posthog]])
  })

  test('only provides the page view capture on a published site', async () => {
    Object.assign(config, {
      posthogProjectApiKey: 'phc_test',
      posthogHost: HOST,
      publicWebFrontendUrl: 'https://baserow.example',
      builderPreviewUrl: 'https://preview.baserow.example',
    })

    await plugin.setup()

    expect(posthog.init).toHaveBeenCalledWith(
      'phc_test',
      getPosthogOptions({ host: HOST, publishedSite: true })
    )
    expect(routerAfterEach).not.toHaveBeenCalled()
    expect(provide).toHaveBeenCalledOnce()
    const [name, capturePublishedPageView] = provide.mock.calls[0]
    expect(name).toBe('capturePublishedPageView')

    const page = { id: 1, path: '/event/:id' }
    capturePublishedPageView(page)

    expect(posthog.capture.mock.calls).toStrictEqual([
      ['$pageview', getPublishedPageViewProperties(window.location, page)],
    ])
    expect(posthog.identify).not.toHaveBeenCalled()
  })
})
