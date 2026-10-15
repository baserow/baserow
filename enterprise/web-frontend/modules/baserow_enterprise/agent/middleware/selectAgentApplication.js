import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

export async function selectAgentApplication(app, to) {
  const { $store, $hasPermission } = app
  const agentId = Number(to.params.agentId)

  try {
    const agent = $store.getters['application/get'](agentId)
    if (!agent || agent.type !== 'agent') {
      throw new StoreItemLookupError('Agent not found.')
    }

    await $store.dispatch('workspace/selectById', agent.workspace.id)
    if (!$hasPermission('application.read', agent, agent.workspace.id)) {
      throw new StoreItemLookupError('Agent not found.')
    }
    await $store.dispatch('application/select', agent)
  } catch (error) {
    const lookupError = error instanceof StoreItemLookupError
    if (!error.response && !lookupError) throw error

    const statusCode = lookupError ? 404 : error.response.status
    throw createError({
      statusCode,
      message:
        statusCode === 404 ? 'Agent not found.' : normalizeError(error).message,
      data: { report: statusCode >= 500 },
      fatal: true,
    })
  }
}

export default defineNuxtRouteMiddleware((to) =>
  selectAgentApplication(useNuxtApp(), to)
)
