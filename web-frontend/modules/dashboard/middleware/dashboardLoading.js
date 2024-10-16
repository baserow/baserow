/**
 * Middleware that changes the dashboard loading state to true before the route
 * changes.
 */
export default async function ({ route, from, store, app }) {
  function parseIntOrNull(x) {
    return x != null ? parseInt(x) : null
  }

  const toDashboardId = parseIntOrNull(route?.params?.dashboardId)
  const fromDashboardId = parseIntOrNull(from?.params?.dashboardId)
  const differentDashboardId = fromDashboardId !== toDashboardId

  if (!from || differentDashboardId) {
    await store.dispatch('dashboardApplication/setLoading', true)
  }
}
