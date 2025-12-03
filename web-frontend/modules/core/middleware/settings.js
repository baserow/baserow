/**
 * This middleware makes sure the settings are fetched and available in the store.
 */
export default defineNuxtRouteMiddleware(async () => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store
  const event = process.server ? useRequestEvent() : null

  // If nuxt generate, pass this middleware
  if (process.server && !event) return

  if (!store.getters['settings/isLoaded']) {
    await store.dispatch('settings/load')
  }
})

/*
Previous Nuxt 2 middleware:
export default async function ({ store, req }) {
  // If nuxt generate, pass this middleware
  if (process.server && !req) return

  if (!store.getters['settings/isLoaded']) {
    await store.dispatch('settings/load')
  }
}
*/
