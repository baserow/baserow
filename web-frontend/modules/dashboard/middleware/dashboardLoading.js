/**
 * Middleware that changes the dashboard loading state to true before the route
 * changes.
 */
export default defineNuxtRouteMiddleware(async (to, from) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store

  function parseIntOrNull(x) {
    return x != null ? parseInt(x) : null
  }

  const toDashboardId = parseIntOrNull(to?.params?.dashboardId)
  const fromDashboardId = parseIntOrNull(from?.params?.dashboardId)
  const differentDashboardId = fromDashboardId !== toDashboardId

  if (!from || differentDashboardId) {
    await store.dispatch('dashboardApplication/setLoading', true)
  }
})
