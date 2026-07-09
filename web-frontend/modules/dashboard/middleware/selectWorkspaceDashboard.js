import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

/**
 * Selects the workspace and dashboard application based on the route parameters.
 * This middleware must only do store lookups and never make network requests on
 * client-side navigation, because it blocks the navigation and would delay the
 * skeleton loading state of the dashboard page.
 */
export default defineNuxtRouteMiddleware(async (to, from) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store

  function parseIntOrNull(x) {
    return x != null ? parseInt(x) : null
  }

  const toDashboardId = parseIntOrNull(to?.params?.dashboardId)

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
      const errorStatus = e.response?.status || 404

      throw createError({
        statusCode: errorStatus,
        message:
          errorStatus === 404
            ? 'Dashboard not found.'
            : normalizeError(e).message,
        data: {
          report: errorStatus !== 404,
        },
        fatal: true,
      })
    }
  }
})
