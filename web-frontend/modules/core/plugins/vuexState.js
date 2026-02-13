/**
 * Plugin to serialize/deserialize Vuex state for SSR hydration
 * This ensures that the Vuex store state is transferred from server to client
 */
export default defineNuxtPlugin({
  name: 'vuex-state',
  dependsOn: ['create-store'],
  setup(nuxtApp) {
    const store = nuxtApp.$store

    // Server-side: Serialize Vuex state to payload after render
    if (import.meta.server) {
      nuxtApp.hook('app:rendered', () => {
        nuxtApp.payload.vuex = store.state
      })
    }

    // Client-side: Restore Vuex state from payload SYNCHRONOUSLY
    // This must happen during plugin setup, not in a hook, because
    // middleware runs before hooks complete and needs access to the
    // hydrated state (e.g., settings.isLoaded, auth.isAuthenticated)
    if (import.meta.client && nuxtApp.payload.vuex) {
      store.replaceState(nuxtApp.payload.vuex)
    }

    // Add helper method for registering modules with proper SSR hydration
    // On client after hydration, use preserveState to keep the hydrated state
    // and avoid "[vuex] state field was overridden" warnings
    store.registerModuleNuxtSafe = (path, module, options = {}) => {
      const shouldPreserveState =
        import.meta.client && nuxtApp.payload.vuex !== undefined
      store.registerModule(path, module, {
        ...options,
        preserveState: shouldPreserveState || options.preserveState,
      })
    }
  },
})
