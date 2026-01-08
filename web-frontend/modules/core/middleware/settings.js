/**
 * This middleware makes sure the settings are fetched and available in the store.
 */
export default defineNuxtRouteMiddleware(async () => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store
  const event = import.meta.server ? useRequestEvent() : null

  // If nuxt generate, pass this middleware
  if (import.meta.server && !event) return

  if (!store.getters['settings/isLoaded']) {
    await store.dispatch('settings/load')
  }
})
