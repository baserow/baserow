import { getDefaultView } from '@baserow/modules/database/utils/view'

import { useNuxtApp } from '#app'

/**
 * Middleware that changes the table loading state to true before the route
 * changes. That way we can show a loading animation to the user when switching
 * between views.

export default async function ({ route, from, store, app }) {
  function parseIntOrNull(x) {
    return x != null ? parseInt(x) : null
  }

  const toDatabaseId = parseIntOrNull(route?.params?.databaseId)
  const toDatabase = store.getters['application/get'](toDatabaseId)

  // If the database is not found, it means that the user has no access to it, or
  // it does not exist. In this case, we don't have to do anything with the table
  // loading state because the table page is going to fail with a 404.
  if (!toDatabase) {
    return
  }

  const toWorkspaceId = toDatabase.workspace.id
  const toTableId = parseIntOrNull(route.params.tableId)
  const toViewId = parseIntOrNull(route.params.viewId)
  const toRowId = parseIntOrNull(route.params.rowId)

  const fromTableId = parseIntOrNull(from?.params?.tableId)
  const fromViewId = parseIntOrNull(from?.params?.viewId)

  const differentTableId = fromTableId !== toTableId
  const differentViewId = fromViewId !== toViewId

  // Table links might not include the viewId in params (viewId is null), but
  // the end result will be to be redirected to the default view, so don't show
  // the loading animation if that's the case.
  const viewToUse = getDefaultView(app, store, toWorkspaceId, toRowId !== null)
  const willRedirectToSameViewId =
    fromViewId && toViewId === null && fromViewId === viewToUse?.id

  if (
    !from ||
    differentTableId ||
    (!differentTableId && differentViewId && !willRedirectToSameViewId)
  ) {
    await store.dispatch('table/setLoading', true)
  }
}*/

export default defineNuxtRouteMiddleware(async (to, from) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store

  function parseIntOrNull(x) {
    return x != null ? parseInt(x) : null
  }

  const toDatabaseId = parseIntOrNull(to.params?.databaseId)
  const toDatabase = store.getters['application/get'](toDatabaseId)

  if (!toDatabase) {
    return
  }

  const toWorkspaceId = toDatabase.workspace.id
  const toTableId = parseIntOrNull(to.params.tableId)
  const toViewId = parseIntOrNull(to.params.viewId)
  const toRowId = parseIntOrNull(to.params.rowId)

  const fromTableId = parseIntOrNull(from?.params?.tableId)
  const fromViewId = parseIntOrNull(from?.params?.viewId)

  const differentTableId = fromTableId !== toTableId
  const differentViewId = fromViewId !== toViewId

  const viewToUse = getDefaultView(
    nuxtApp,
    store,
    toWorkspaceId,
    toRowId !== null
  )

  const willRedirectToSameViewId =
    fromViewId && toViewId === null && fromViewId === viewToUse?.id

  if (
    !from ||
    differentTableId ||
    (!differentTableId && differentViewId && !willRedirectToSameViewId)
  ) {
    await store.dispatch('table/setLoading', true)
  }
})
