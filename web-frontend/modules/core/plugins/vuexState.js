/**
 * Plugin to serialize/deserialize Vuex state for SSR hydration
 * This ensures that the Vuex store state is transferred from server to client
 */
export default defineNuxtPlugin({
  name: 'vuex-state',
  dependsOn: ['create-store'],
  setup(nuxtApp) {
    const store = nuxtApp.$store

    // Server-side: Serialize Vuex state to payload
    if (import.meta.server) {
      nuxtApp.hook('app:rendered', () => {
        nuxtApp.payload.vuex = store.state
      })
    }

    // Client-side: Restore Vuex state from payload
    if (import.meta.client) {
      nuxtApp.hook('app:created', () => {
        if (nuxtApp.payload.vuex) {
          store.replaceState(nuxtApp.payload.vuex)
        }
      })
    }
  },
})
