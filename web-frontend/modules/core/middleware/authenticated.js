/**
 * If this middleware is added to a page, it will redirect back to the login
 * page if the user is not authenticated.
 */
export default defineNuxtRouteMiddleware((to) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store
  const event = import.meta.server ? useRequestEvent() : null

  if (import.meta.server && !event) return

  if (!store.getters['auth/isAuthenticated']) {
    const original =
      import.meta.server && event?.node?.req
        ? event.node.req.originalUrl || event.node.req.url || to.fullPath
        : to.fullPath
    const query = { original: encodeURI(original) }

    return navigateTo({ name: 'login', query })
  }
})
