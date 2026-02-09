/**
 * This middleware makes sure that the current user is staff else a 403 error
 * will be shown to the user.
 */
export default defineNuxtRouteMiddleware(() => {
  const { $store } = useNuxtApp()

  const event = import.meta.server ? useRequestEvent() : null

  // If nuxt generate, pass this middleware
  if (import.meta.server && !event) return

  // If the user is not staff we want to show a forbidden error.
  if (!$store.getters['auth/isStaff']) {
    throw createError({ statusCode: 403, message: 'Forbidden.' })
  }
})
