import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

/**
 * Selects the dashboard and workspace of the route params. Everything else the
 * dashboard page needs is fetched by the page itself, so that it can render its
 * skeleton loading state without waiting for the network.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store

  const toDashboardId = to.params?.dashboardId
    ? parseInt(to.params.dashboardId)
    : null

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
