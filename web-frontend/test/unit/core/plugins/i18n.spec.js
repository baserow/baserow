// @vitest-environment node
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { nextTick, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

const env = vi.hoisted(() => ({
  currentMomentLocale: 'en',
  localeLoads: {},
  watchStops: [],
}))

vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    watch(...args) {
      const stop = actual.watch(...args)
      env.watchStops.push(stop)
      return stop
    },
  }
})

vi.mock('@baserow/modules/core/moment', () => ({
  default: {
    locale: (locale) => {
      env.currentMomentLocale = locale
    },
  },
  loadMomentLocale: async (locale) => {
    if (env.localeLoads[locale]) {
      await env.localeLoads[locale].promise
      // Real Moment locale modules select themselves when they register.
      env.currentMomentLocale = locale
    }
  },
}))

const { default: plugin } = await import('@baserow/modules/core/plugins/i18n')

function deferred() {
  let resolve, reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('lazy Moment locale changes', () => {
  let nuxtApp

  beforeEach(() => {
    env.currentMomentLocale = 'en'
    env.localeLoads = {}
    env.watchStops = []
    nuxtApp = {
      $i18n: {
        locale: ref('en'),
        fallbackLocale: ref(null),
        loadLocaleMessages: vi.fn().mockResolvedValue(),
      },
    }
  })

  afterEach(() => {
    env.watchStops.forEach((stop) => stop())
    vi.restoreAllMocks()
  })

  test('keeps the latest language when older locale imports complete last', async () => {
    env.localeLoads.fr = deferred()
    env.localeLoads.de = deferred()
    await plugin.setup(nuxtApp)

    nuxtApp.$i18n.locale.value = 'fr'
    await nextTick()
    nuxtApp.$i18n.locale.value = 'de'
    await nextTick()
    env.localeLoads.de.resolve()
    await flushPromises()
    expect(env.currentMomentLocale).toBe('de')

    env.localeLoads.fr.resolve()
    await flushPromises()

    expect(env.currentMomentLocale).toBe('de')
    expect(nuxtApp.$i18n.fallbackLocale.value).toBe('en')
    expect(nuxtApp.$i18n.loadLocaleMessages).toHaveBeenCalledWith('en')
  })

  test('preserves a switch back to English while another locale is still loading', async () => {
    env.localeLoads.fr = deferred()
    await plugin.setup(nuxtApp)

    nuxtApp.$i18n.locale.value = 'fr'
    await nextTick()
    nuxtApp.$i18n.locale.value = 'en'
    await nextTick()
    env.localeLoads.fr.resolve()
    await flushPromises()

    expect(env.currentMomentLocale).toBe('en')
  })

  test('handles an unavailable locale chunk during startup', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const error = new Error('locale unavailable')
    nuxtApp.$i18n.locale.value = 'fr'
    env.localeLoads.fr = deferred()
    const setup = plugin.setup(nuxtApp)
    env.localeLoads.fr.reject(error)

    await expect(setup).resolves.toBeUndefined()
    expect(warning).toHaveBeenCalledWith('Failed to load Moment locale:', error)
    expect(nuxtApp.$i18n.loadLocaleMessages).toHaveBeenCalledWith('en')
  })

  test('handles an unavailable locale chunk during a language switch', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const error = new Error('locale unavailable')
    env.localeLoads.fr = deferred()
    await plugin.setup(nuxtApp)

    nuxtApp.$i18n.locale.value = 'fr'
    await nextTick()
    env.localeLoads.fr.reject(error)
    await flushPromises()

    expect(warning).toHaveBeenCalledWith('Failed to load Moment locale:', error)
    expect(nuxtApp.$i18n.loadLocaleMessages).toHaveBeenCalledWith('en')
  })
})
