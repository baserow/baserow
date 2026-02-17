import { StoreItemLookupError } from '@baserow/modules/core/errors'

/**
 * Middleware that changes the dashboard loading state to true before the route
 * changes.
 */
export default defineNuxtRouteMiddleware(async (to, from) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store
  const { $i18n } = nuxtApp

  function parseIntOrNull(x) {
    return x != null ? parseInt(x) : null
  }

  const toDashboardId = parseIntOrNull(to?.params?.dashboardId)
  const fromDashboardId = parseIntOrNull(from?.params?.dashboardId)
  const differentDashboardId = fromDashboardId !== toDashboardId

  if (toDashboardId) {
    try {
      const dashboard = await store.dispatch(
        'application/selectById',
        toDashboardId
      )
      await store.dispatch('workspace/selectById', dashboard.workspace.id)
    } catch (e) {
      if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
        throw e
      }

      throw createError({
        statusCode: 404,
        message: 'Dashboard not found.',
        fatal: false,
      })
    }
  }

  // If it's the first page or the server side rendered page, then always put the
  // dashboard in the loading state for the correct animation.
  if (import.meta.server || !from || differentDashboardId) {
    await store.dispatch('dashboardApplication/setLoading', true)
  }
})
