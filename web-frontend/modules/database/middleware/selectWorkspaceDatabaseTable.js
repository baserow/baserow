import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'
import { getDefaultView } from '@baserow/modules/database/utils/view'

export default defineNuxtRouteMiddleware(async (to, from) => {
  const nuxtApp = useNuxtApp()
  const { $store, $registry } = nuxtApp

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
    if (e.response === undefined && !(e instanceof StoreItemLookupError))
      throw e
    throw createError({
      statusCode: e.response?.status || 404,
      message: normalizeError(e).message,
    })
  }

  // Fetch views only if the table has changed because there is no need
  // to fetch them if the view or row changes.
  if ($store.state.view.tableId !== table.id) {
    await $store.dispatch('view/fetchAll', table)
  }

  // If the viewId is not provided, redirect to the default view. This prevents the
  // page component from being created twice.
  if (viewId === null) {
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

  // In some cases, the backend needs the view ID to scope which fields to list.
  // This can happen when a user does not have full access to a table for
  // example.
  const view = $store.getters['view/get'](viewId)
  let fieldsRequireViewId = false
  if (view) {
    const ownershipType = $registry.get(
      'viewOwnershipType',
      view.ownership_type
    )
    fieldsRequireViewId = ownershipType.fetchingFieldsRequiresViewId(
      database,
      table,
      view
    )
  }
  const fieldCheckViewId = fieldsRequireViewId ? viewId : null
  const fieldsLoadedFor = $store.getters['field/isLoadedFor'](
    tableId,
    fieldCheckViewId
  )
  if (!fieldsLoadedFor) {
    await $store.dispatch('field/fetchAll', {
      table,
      viewId: fieldCheckViewId,
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
