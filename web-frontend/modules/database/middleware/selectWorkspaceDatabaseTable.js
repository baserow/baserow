import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'
import { getDefaultView } from '@baserow/modules/database/utils/view'

/**
 * Selects the workspace, database and table based on the route parameters. This
 * middleware must only do store lookups and never make network requests on
 * client-side navigation, because it blocks the navigation and would delay the
 * skeleton loading state of the table page. Fetching the views, fields and row
 * is done in the `usePageAsyncData` handler of the table page.
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

  // If the viewId is not provided, redirect to the default view. This prevents the
  // page component from being created twice. On the server it's okay to fetch the
  // views blocking because the first request always waits for the fully rendered
  // page anyway, and this way the server responds with a redirect. On the client
  // this only happens when the views of the table are already in the store,
  // otherwise the table page fetches them and handles the redirect itself without
  // blocking the navigation.
  if (viewId === null) {
    if (import.meta.server && $store.state.view.tableId !== table.id) {
      await $store.dispatch('view/fetchAll', table)
    }

    if ($store.state.view.tableId === table.id) {
      const rowId = to.params.rowId ? parseInt(to.params.rowId) : null
      const defaultView = getDefaultView(
        nuxtApp,
        $store,
        database.workspace.id,
        rowId !== null
      )

      if (defaultView) {
        return nuxtApp.runWithContext(() =>
          navigateTo({
            name: to.name,
            params: { ...to.params, viewId: defaultView.id },
            query: to.query,
          })
        )
      }
    }
  }
})
