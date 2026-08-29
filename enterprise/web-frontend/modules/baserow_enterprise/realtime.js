/**
 * Registers the real time events related to the baserow_enterprise module. When a message
 * comes in, the state of the stores will be updated to match the latest update.
 */

export const registerRealtimeEvents = (realtime) => {
  const updateWorkspacePermissions = async (store, workspaceId) => {
    const workspace = store.getters['workspace/get'](workspaceId)
    if (workspace) {
      try {
        await store.dispatch('workspace/forceFetchPermissions', workspace)
      } catch (e) {
        await store.dispatch('toast/setPermissionsUpdated', true)
      }
    }
  }

  realtime.registerEvent(
    'permissions_updated',
    ({ store }, { workspace_id: workspaceId }) => {
      updateWorkspacePermissions(store, workspaceId)
    }
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

      updateWorkspacePermissions(store, workspaceId)
    }
  )

  realtime.registerEvent('agent_chat_updated', ({ store }, { chat }) => {
    store.dispatch('agentHistory/forceUpdateChat', { chat })
    store.dispatch('agentChat/handleChatUpdated', { chat })
  })

  realtime.registerEvent(
    'agent_chat_event',
    ({ store }, { chat_id: chatId, event }) => {
      store.dispatch('agentChat/handleRealtimeEvent', { chatId, event })
    }
  )

  realtime.registerEvent(
    'agent_chat_deleted',
    ({ store }, { chat_id: chatId }) => {
      store.dispatch('agentHistory/forceDeleteChat', { chatId })
      store.dispatch('agentChat/handleChatDeleted', { chatId })
    }
  )

  // Broadcast workspace-wide so the sidebar badge and header button stay in
  // sync for everybody, not only for users on the agent page.
  realtime.registerEvent(
    'agent_pending_approvals_updated',
    ({ store }, { application_id: applicationId, count }) => {
      const application = store.getters['application/get'](applicationId)
      if (application !== undefined) {
        store.dispatch('application/forceUpdate', {
          application,
          data: { pending_approvals_count: count },
        })
      }
    }
  )

  realtime.registerEvent('agent_definition_updated', ({ store }, { agent }) => {
    store.dispatch('agentApplication/forceUpdate', { values: agent })
  })

  realtime.registerEvent(
    'agent_configuration_updated',
    ({ store }, { application_id: applicationId }) => {
      const agent = store.getters['agentApplication/getAgent']
      if (agent?.application_id === applicationId) {
        store.dispatch('agentApplication/fetchTriggers', { applicationId })
        store.dispatch('agentApplication/fetchTools', { applicationId })
        store.dispatch('agentApplication/fetchChannels', { applicationId })
      }
    }
  )
}
