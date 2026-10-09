import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

export async function selectAgentBuilder(app, to) {
  const { $store, $hasPermission } = app
  const agentBuilderId = Number(to.params.agentBuilderId)
  const agentId = to.params.agentId ? Number(to.params.agentId) : null

  try {
    const agentBuilder = $store.getters['application/get'](agentBuilderId)
    if (!agentBuilder || agentBuilder.type !== 'agent_builder') {
      throw new StoreItemLookupError('Agent Builder not found.')
    }

    await $store.dispatch('workspace/selectById', agentBuilder.workspace.id)
    if (
      !$hasPermission(
        'agent_builder.list_agents',
        agentBuilder,
        agentBuilder.workspace.id
      )
    ) {
      throw new StoreItemLookupError('Agent Builder not found.')
    }

    await $store.dispatch('agentBuilderAgent/fetch', agentBuilder)
    if (agentId !== null) {
      await $store.dispatch('agentBuilderAgent/read', { agentBuilder, agentId })
    }
    await $store.dispatch('application/select', agentBuilder)
    await $store.dispatch('agentBuilderAgent/select', agentId)
  } catch (error) {
    const lookupError = error instanceof StoreItemLookupError
    if (!error.response && !lookupError) throw error

    const statusCode = lookupError ? 404 : error.response.status
    throw createError({
      statusCode,
      message:
        statusCode === 404
          ? 'Agent Builder not found.'
          : normalizeError(error).message,
      data: { report: statusCode >= 500 },
      fatal: true,
    })
  }
}

export default defineNuxtRouteMiddleware((to) =>
  selectAgentBuilder(useNuxtApp(), to)
)
