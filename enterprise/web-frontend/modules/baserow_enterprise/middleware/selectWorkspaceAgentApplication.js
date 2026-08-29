import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

export default defineNuxtRouteMiddleware(async (to) => {
  const { $store } = useNuxtApp()

  const agentApplicationId = parseInt(to.params.agentApplicationId)

  try {
    const application = await $store.dispatch(
      'application/selectById',
      agentApplicationId
    )

    await $store.dispatch('workspace/selectById', application.workspace.id)
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
        errorStatus === 404 ? 'Agent not found.' : normalizeError(e).message,
      data: {
        report: errorStatus !== 404,
      },
      fatal: true,
    })
  }
})
