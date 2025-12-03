/**
 * This middleware makes sure that the current user is staff else a 403 error
 * will be shown to the user.
 */
export default defineNuxtRouteMiddleware(() => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store
  const event = process.server ? useRequestEvent() : null

  // If nuxt generate, pass this middleware
  if (process.server && !event) return

  // If the user is not staff we want to show a forbidden error.
  if (!store.getters['auth/isStaff']) {
    throw createError({ statusCode: 403, message: 'Forbidden.' })
  }
})

/*
Previous Nuxt 2 middleware:
export default function ({ store, req, error }) {
  // If nuxt generate, pass this middleware
  if (process.server && !req) return

  // If the user is not staff we want to show a forbidden error.
  if (!store.getters['auth/isStaff']) {
    return error({ statusCode: 403, message: 'Forbidden.' })
  }
}
*/
