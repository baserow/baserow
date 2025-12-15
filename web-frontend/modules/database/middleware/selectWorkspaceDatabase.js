export default defineNuxtRouteMiddleware((to, from) => {
  console.log('Navigating to:', to.path)
  console.log('Params:', to.params)
  console.log('Query:', to.query)
  console.log('Page meta:', to.meta)

  // Example: check meta
  if (to.meta.requiresAuth && !isLoggedIn()) {
    return navigateTo('/login')
  }
})
