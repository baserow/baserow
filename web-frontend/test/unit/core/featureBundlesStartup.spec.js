import { expect, test, vi } from 'vitest'
import initializeFeatures from '@baserow/modules/core/plugins/featureBundles'
import {
  isFeatureBundleLoaded,
  loadFeatureBundle,
  registerFeatureBundle,
} from '@baserow/modules/core/utils/featureBundles'

test('waits for feature initialization to finish before startup completes', async () => {
  const app = { $config: { public: {} } }
  let finishLoading
  const load = vi.fn(
    () =>
      new Promise((resolve) => {
        finishLoading = resolve
      })
  )
  registerFeatureBundle(app, 'database', load)
  let started = false
  const startup = initializeFeatures(app).then(() => {
    started = true
  })

  await vi.waitFor(() => expect(load).toHaveBeenCalledOnce())
  expect(started).toBe(false)
  finishLoading({})
  await startup
  expect(started).toBe(true)
})

test.each([undefined, false, 'false'])(
  'initializes all features before rendering when lazy loading is %s',
  async (setting) => {
    const app = {
      $config: { public: { baserowFrontendLazyFeatures: setting } },
    }
    const registrations = []
    registerFeatureBundle(app, 'database', async () => {
      registrations.push('database')
      return { Database: {} }
    })
    registerFeatureBundle(app, 'database', async () => {
      registrations.push('premium database')
      return { PremiumDatabase: {} }
    })
    registerFeatureBundle(app, 'onboarding', async () => {
      registrations.push('onboarding')
      return {}
    })

    await initializeFeatures(app)

    expect(registrations).toEqual([
      'database',
      'premium database',
      'onboarding',
    ])
    expect(isFeatureBundleLoaded(app, 'database')).toBe(true)
    expect(isFeatureBundleLoaded(app, 'onboarding')).toBe(true)
    expect(Object.keys(await loadFeatureBundle(app, 'database'))).toEqual([
      'Database',
      'PremiumDatabase',
    ])
    expect(registrations).toHaveLength(3)
  }
)

test.each([true, 'true'])(
  'defers features until requested when lazy loading is %s',
  async (setting) => {
    const app = {
      $config: { public: { baserowFrontendLazyFeatures: setting } },
    }
    const loadDatabase = vi.fn(async () => ({}))
    registerFeatureBundle(app, 'database', loadDatabase)

    await initializeFeatures(app)

    expect(isFeatureBundleLoaded(app, 'database')).toBe(false)
    expect(loadDatabase).not.toHaveBeenCalled()
    await loadFeatureBundle(app, 'database')
    expect(isFeatureBundleLoaded(app, 'database')).toBe(true)
    expect(loadDatabase).toHaveBeenCalledOnce()
  }
)
