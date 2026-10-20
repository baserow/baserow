import { defineAsyncComponent } from 'vue'
import { tryUseNuxtApp, useLoadingIndicator } from '#imports'

let pendingLoads = 0

/**
 * Runs the loader while showing the top progress bar, so that the user sees that
 * something is happening while a chunk downloads on a slow connection. The
 * indicator is only shown if loading takes longer than its throttle, so cached
 * chunks don't make it flash.
 */
export async function withLoadingIndicator(loader) {
  const nuxtApp = import.meta.client ? tryUseNuxtApp() : null
  if (!nuxtApp) {
    return await loader()
  }

  const indicator = nuxtApp.runWithContext(() => useLoadingIndicator())
  if (pendingLoads++ === 0) {
    indicator.start()
  }
  try {
    return await loader()
  } finally {
    if (--pendingLoads === 0) {
      indicator.finish()
    }
  }
}

/**
 * Registry types return their components through this, so that the components
 * and their dependencies are split into separate chunks instead of being part of
 * the entry chunk. It must be called once at module level, not inside a getter,
 * otherwise every call returns a new component and Vue remounts it.
 *
 * Usage: `const GridView = lazyComponent(() => import('.../GridView'))`
 *
 * Custom component options that are read without rendering the component, like
 * the `height` of a card component, can't be read before the component has been
 * loaded, so they must be provided as `staticOptions` instead.
 */
export function lazyComponent(loader, staticOptions = {}) {
  return Object.assign(
    defineAsyncComponent({
      loader: () => withLoadingIndicator(loader),
    }),
    staticOptions
  )
}

/**
 * Returns the loaded component behind a lazy component, or the given component
 * if it's not loaded yet or not lazy. It must not be used to choose the component
 * to render: the result changes once the chunk has loaded, which makes Vue
 * remount the component and lose its state, and it can differ between the server
 * and the client, which breaks hydration.
 */
export function unwrapLazyComponent(component) {
  return component?.__asyncResolved || component
}
