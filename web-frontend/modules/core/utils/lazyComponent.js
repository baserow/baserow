import { defineAsyncComponent } from 'vue'
import { tryUseNuxtApp, useLoadingIndicator } from '#imports'

const pendingLoads = new WeakMap()

/**
 * Show the existing top progress bar until all feature loads in this app settle.
 * Its configured throttle prevents flashes for cached imports. Skip SSR and
 * initial hydration so app.vue configures the indicator before its first use.
 */
export async function withLoadingIndicator(loader) {
  const app = import.meta.client ? tryUseNuxtApp() : null
  if (!app || app.isHydrating) {
    return await loader()
  }

  const indicator = app.runWithContext(() => useLoadingIndicator())
  const pending = pendingLoads.get(app) || 0
  pendingLoads.set(app, pending + 1)
  if (pending === 0) indicator.start()
  try {
    return await loader()
  } finally {
    const remaining = pendingLoads.get(app) - 1
    if (remaining === 0) {
      pendingLoads.delete(app)
      indicator.finish()
    } else {
      pendingLoads.set(app, remaining)
    }
  }
}

/** Keep module-level component identity while reporting grouped bundle loads. */
export function lazyComponent(loader) {
  return defineAsyncComponent(() => withLoadingIndicator(loader))
}
