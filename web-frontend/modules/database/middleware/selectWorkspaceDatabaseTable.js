import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

/**
 * Selects the workspace, database and table of the route params, and fetches the
 * row of the row modal if there is one. Everything else the table page needs is
 * fetched by the page itself, so that it can render its skeleton loading state
 * without waiting for the network.
 */
export default defineNuxtRouteMiddleware(async (to, from) => {
  const nuxtApp = useNuxtApp()
  const { $store } = nuxtApp

  const databaseId = parseInt(to.params.databaseId)
  const tableId = parseInt(to.params.tableId)
  const viewId = to.params.viewId ? parseInt(to.params.viewId) : null

  let database, table
  try {
    const result = await $store.dispatch('table/selectById', {
      databaseId,
      tableId,
    })
    database = result.database
    table = result.table
    await $store.dispatch('workspace/selectById', database.workspace.id)
  } catch (e) {
    const isStoreLookupError = e instanceof StoreItemLookupError
    if (e.response === undefined && !isStoreLookupError) {
      throw e
    }

    const errorStatus =
      isStoreLookupError || !e.response?.status ? 404 : e.response.status

    throw createError({
      statusCode: errorStatus,
      message:
        errorStatus === 404 ? 'Table not found.' : normalizeError(e).message,
      data: {
        report: errorStatus !== 404,
      },
      fatal: true,
    })
  }

  // Handle enlarged row modal state by already fetching the row if needed because
  // it's provided in the params.
  const rowId = to.params.rowId ? parseInt(to.params.rowId) : null
  if (rowId) {
    const row = await $store.dispatch('rowModalNavigation/fetchRow', {
      tableId: table.id,
      rowId,
      viewId,
    })

    // If fetch failed, redirect to table without rowId so that the table is still
    // visible.
    if (!row) {
      return nuxtApp.runWithContext(() =>
        navigateTo(
          {
            name: 'database-table',
            params: { ...to.params, rowId: '' },
            query: to.query,
          },
          { replace: true }
        )
      )
    }
  } else {
    // If no rowId is provided, then we want to make 100% sure any old rows are
    // cleared. This could be the case when a row is open, but the user navigates
    // to page without selected row.
    await $store.dispatch('rowModalNavigation/clearRow')
  }
})
