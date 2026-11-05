import { defineComponent, h, shallowReactive } from 'vue'
import { useNuxtApp } from '#imports'
import {
  lazyComponent,
  withLoadingIndicator,
} from '@baserow/modules/core/utils/lazyComponent'

const features = new WeakMap()
const deferredComponents = new Map()

/** Keep registrations and initialization isolated between Nuxt SSR requests. */
function getState(app) {
  if (!features.has(app)) {
    features.set(app, {
      loaders: new Map(),
      pending: new Map(),
      components: shallowReactive({}),
    })
  }
  return features.get(app)
}

/** Append a feature or its premium/enterprise extension in order. */
export function registerFeatureBundle(app, type, loader) {
  const state = getState(app)
  if (!state.loaders.has(type)) state.loaders.set(type, [])
  state.loaders.get(type).push(loader)
}

/** Whether a feature opted into deferred initialization. */
export function hasFeatureBundle(app, type) {
  return getState(app).loaders.has(type)
}

/** True for initialized features and third-party types without a lazy entry. */
export function isFeatureBundleLoaded(app, type) {
  const state = getState(app)
  return !state.loaders.has(type) || Boolean(state.components[type])
}

/**
 * Initialize a feature's stores, registry types, and extensions once per app.
 * Concurrent route/component requests share the same promise. Imported modules
 * may be cached globally, but their registration functions run for every SSR app.
 */
export async function loadFeatureBundle(app, type) {
  const state = getState(app)
  if (!state.loaders.has(type)) return {}
  if (!state.pending.has(type)) {
    const initialize = async () => {
      const components = {}
      for (const loader of state.loaders.get(type)) {
        Object.assign(components, await loader(app))
      }
      state.components[type] = components
      return components
    }
    state.pending.set(
      type,
      app.runWithContext
        ? app.runWithContext(() => withLoadingIndicator(initialize))
        : initialize()
    )
  }
  return await state.pending.get(type)
}

/** Load all feature registrations for the existing full-application unit fixtures. */
export async function loadAllFeatureBundles(app) {
  for (const type of getState(app).loaders.keys()) {
    await loadFeatureBundle(app, type)
  }
}

/**
 * Return the real component after initialization, or a stable deferred wrapper.
 * Registration belongs in setup rather than the cached async loader: a new SSR
 * request still needs its own stores when another request already loaded the UI.
 */
export function getFeatureComponent(app, type, name) {
  const component = getState(app).components[type]?.[name]
  if (component) return component
  const key = `${type}:${name}`
  if (!deferredComponents.has(key)) {
    const wrapper = defineComponent({
      name: `Deferred${name}`,
      inheritAttrs: false,
      async setup(_, { attrs, slots }) {
        const components = await loadFeatureBundle(useNuxtApp(), type)
        if (!components[name])
          throw new Error(`Missing ${type} component ${name}`)
        return () => h(components[name], attrs, slots)
      },
    })
    deferredComponents.set(
      key,
      lazyComponent(async () => wrapper)
    )
  }
  return deferredComponents.get(key)
}
