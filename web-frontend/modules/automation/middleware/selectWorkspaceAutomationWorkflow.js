import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

export default defineNuxtRouteMiddleware(async (to) => {
  const { $store } = useNuxtApp()

  const automationId = parseInt(to.params.automationId)
  const workflowId = parseInt(to.params.workflowId)

  try {
    const automation = await $store.dispatch(
      'application/selectById',
      automationId
    )

    await $store.dispatch('workspace/selectById', automation.workspace.id)

    await $store.dispatch('automationWorkflow/selectById', {
      automation,
      workflowId,
    })
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
        errorStatus === 404
          ? 'Automation workflow not found.'
          : normalizeError(e).message,
      data: {
        report: errorStatus !== 404,
      },
      fatal: true,
    })
  }
})
