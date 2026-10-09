/**
 * Registers the real time events related to the baserow_enterprise module. When a message
 * comes in, the state of the stores will be updated to match the latest update.
 */

import { generateHash } from '@baserow/modules/core/utils/hashing'

export const registerRealtimeEvents = (realtime) => {
  for (const event of ['created', 'updated']) {
    realtime.registerEvent(
      `agent_builder_agent_${event}`,
      ({ store }, { agent }) => {
        const agentBuilder = store.getters['application/get'](
          agent.agent_builder_id
        )
        if (agentBuilder?.type === 'agent_builder') {
          store.dispatch('agentBuilderAgent/forceUpsert', {
            agentBuilder,
            agent,
          })
        }
      }
    )
  }
  realtime.registerEvent(
    'agent_builder_agents_reordered',
    ({ store }, { agent_builder_id: builderId, order }) => {
      const agentBuilder = store.getters['application/getAll'].find(
        (application) =>
          application.type === 'agent_builder' &&
          generateHash(application.id) === builderId
      )
      if (agentBuilder) {
        store.commit('agentBuilderAgent/ORDER_AGENTS', { agentBuilder, order })
      }
    }
  )
  realtime.registerEvent(
    'agent_builder_agent_deleted',
    ({ store }, { agent_builder_id: builderId, agent_id: agentId }) => {
      const agentBuilder = store.getters['application/get'](builderId)
      if (agentBuilder?.type === 'agent_builder') {
        store.dispatch('agentBuilderAgent/forceDelete', {
          agentBuilder,
          agentId,
        })
      }
    }
  )

  const updateWorkspacePermissions = async (store, workspaceId, app) => {
    const workspace = store.getters['workspace/get'](workspaceId)
    if (workspace) {
      for (const application of store.getters['application/getAllOfWorkspace'](
        workspace
      )) {
        if (
          application.type === 'agent_builder' &&
          !store.getters['application/isSelected'](application)
        ) {
          store.commit('agentBuilderAgent/SET_AGENTS', {
            agentBuilder: application,
            agents: [],
          })
        }
      }
      try {
        await store.dispatch('workspace/forceFetchPermissions', workspace)
        const agentBuilder = store.getters['application/getSelected']
        if (
          agentBuilder?.type === 'agent_builder' &&
          agentBuilder.workspace.id === workspaceId
        ) {
          const canList = app.$hasPermission(
            'agent_builder.list_agents',
            agentBuilder,
            workspaceId
          )
          if (!canList) {
            store.commit('agentBuilderAgent/SET_AGENTS', {
              agentBuilder,
              agents: [],
            })
            await store.dispatch('agentBuilderAgent/select', null)
            await app.$router.push({
              name: 'workspace',
              params: { workspaceId },
            })
          } else {
            await store.dispatch('agentBuilderAgent/fetch', agentBuilder)
            const agentId = store.getters['agentBuilderAgent/getSelectedId']
            if (
              agentId !== null &&
              !agentBuilder.agents.some(({ id }) => id === agentId) &&
              store.getters['application/isSelected'](agentBuilder)
            ) {
              await store.dispatch('agentBuilderAgent/select', null)
              await app.$router.push({
                name: 'agent-builder',
                params: { agentBuilderId: agentBuilder.id },
              })
            }
          }
        }
      } catch (e) {
        await store.dispatch('toast/setPermissionsUpdated', true)
      }
    }
  }

  realtime.registerEvent(
    'permissions_updated',
    ({ store, app }, { workspace_id: workspaceId }) =>
      updateWorkspacePermissions(store, workspaceId, app)
  )

  realtime.registerEvent(
    'field_permissions_updated',
    ({ store, app }, payload) => {
      const {
        workspace_id: workspaceId,
        field_id: fieldId,
        role,
        allow_in_forms: allowInForms,
      } = payload

      app.$bus.$emit('field-permissions-updated', {
        fieldId,
        role,
        allowInForms,
      })

      updateWorkspacePermissions(store, workspaceId, app)
    }
  )
}
