import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'
import { getDefaultView } from '@baserow/modules/database/utils/view'

export default defineNuxtRouteMiddleware(async (to, from) => {
  const nuxtApp = useNuxtApp()
  const { $store } = nuxtApp

  const databaseId = parseInt(to.params.databaseId)
  const tableId = parseInt(to.params.tableId)

  // Select the table
  try {
    const { database } = await $store.dispatch('table/selectById', {
      databaseId,
      tableId,
    })
    await $store.dispatch('workspace/selectById', database.workspace.id)
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
