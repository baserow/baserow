import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'
import { getDefaultView } from '@baserow/modules/database/utils/view'

export default defineNuxtRouteMiddleware(async (to, from) => {
  const nuxtApp = useNuxtApp()
  const { $store } = nuxtApp

  const databaseId = parseInt(to.params.databaseId)
  const tableId = parseInt(to.params.tableId)
  const viewId = to.params.viewId ? parseInt(to.params.viewId) : null

  // Select the table
  try {
    const { database, table } = await $store.dispatch('table/selectById', {
      databaseId,
      tableId,
    })
    await $store.dispatch('workspace/selectById', database.workspace.id)

    // Fetch views and fields if the table has changed
    if ($store.state.view.tableId !== table.id) {
      await $store.dispatch('view/fetchAll', table)
      await $store.dispatch('field/fetchAll', table)
    }

    // If no viewId is provided, redirect to the default view
    // This prevents the page component from being created twice
    if (viewId === null) {
      const rowId = to.params.rowId ? parseInt(to.params.rowId) : null
      const defaultView = getDefaultView(
        nuxtApp,
        $store,
        database.workspace.id,
        rowId !== null
      )

      if (defaultView) {
        // Redirect to the same route but with the viewId
        // Using navigateTo with replace: true to avoid adding to browser history
        return navigateTo(
          {
            name: to.name,
            params: { ...to.params, viewId: defaultView.id },
            query: to.query,
          },
          { replace: true }
        )
      }
    }

    // Fetch row if rowId is provided
    // This centralizes all data fetching in middleware
    const rowId = to.params.rowId ? parseInt(to.params.rowId) : null
    if (rowId) {
      await $store.dispatch('rowModalNavigation/fetchRow', {
        tableId: table.id,
        rowId,
      })
    }
  } catch (e) {
    if (e.response === undefined && !(e instanceof StoreItemLookupError))
      throw e
    throw createError({
      statusCode: 404,
      message: normalizeError(e).message,
      fatal: false,
    })
  }
})
