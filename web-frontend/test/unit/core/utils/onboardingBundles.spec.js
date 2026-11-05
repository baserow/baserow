import { expect, test, vi } from 'vitest'
import { createStore } from 'vuex'
import { Registry } from '@baserow/modules/core/registry'
import {
  loadFeatureBundle,
  registerFeatureBundle,
} from '@baserow/modules/core/utils/featureBundles'

/** Isolate onboarding startup from the eagerly initialized TestApp fixtures. */
function makeApp() {
  const app = {
    $registry: new Registry(),
    $store: createStore({}),
    $i18n: { t: (key) => key },
  }
  app.$registry.registerNamespace('onboarding')
  for (const load of [
    () => import('@baserow/modules/core/onboardingBundle'),
    () => import('@baserow/modules/database/onboardingBundle'),
  ]) {
    registerFeatureBundle(app, 'onboarding', async (context) => {
      const bundle = await load()
      await bundle.default(context)
      return bundle
    })
  }
  registerFeatureBundle(app, 'onboarding-rendering', async (context) => {
    const bundle =
      await import('@baserow/modules/database/onboardingRenderingBundle')
    await bundle.default(context)
    return bundle
  })
  return app
}

test('onboarding choices and initial forms initialize without the Database editor', async () => {
  const app = makeApp()
  const database = vi.fn(async () => ({}))
  registerFeatureBundle(app, 'database', database)
  await loadFeatureBundle(app, 'onboarding')
  expect(Object.keys(app.$registry.getAll('databaseOnboardingStep'))).toEqual([
    'scratch',
    'import',
    'airtable',
    'template',
  ])
  expect(
    app.$registry.get('onboarding', 'database').getFormComponent().name
  ).toBe('DatabaseStep')
  expect(app.$registry.get('onboarding', 'more').getFormComponent().name).toBe(
    'MoreStep'
  )
  expect(database).not.toHaveBeenCalled()
  expect(app.$store.hasModule('field')).toBe(false)
})

test('rendering-dependent steps load Database once before exposing their real form methods', async () => {
  const app = makeApp()
  const database = vi.fn(async () => ({}))
  registerFeatureBundle(app, 'database', database)
  await loadFeatureBundle(app, 'onboarding')
  const step = app.$registry.get('onboarding', 'database_scratch_track_fields')
  await step.load()
  await app.$registry.get('onboarding', 'database_scratch_import').load()
  expect(database).toHaveBeenCalledOnce()
  expect(step.getFormComponent().methods.isValid).toBeTypeOf('function')
  expect(
    app.$registry
      .get('onboardingTrackFields', 'database_scratch_track_fields_custom')
      .getType()
  ).toBe('database_scratch_track_fields_custom')
})

test('cached onboarding imports register separately for each SSR request', async () => {
  const first = makeApp()
  const second = makeApp()
  await loadFeatureBundle(first, 'onboarding')
  expect(second.$registry.getAll('onboarding')).toEqual({})
  await loadFeatureBundle(second, 'onboarding')
  expect(first.$registry.get('onboarding', 'database')).not.toBe(
    second.$registry.get('onboarding', 'database')
  )
})
