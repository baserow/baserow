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

  // Public web chat: the backend only sends answers and a coarse status.
  realtime.registerEvent('public_agent_chat_event', ({ store }, { event }) => {
    store.dispatch('publicAgentChat/handleEvent', event)
  })
  realtime.registerEvent(
    'public_agent_chat_status',
    ({ store }, { status }) => {
      store.dispatch('publicAgentChat/handleStatus', status)
    }
  )

  // While the next agent's page loads, the previous page is still
  // subscribed; events of another agent must not land in the new stores.
  const isCurrentAgent = (store, agentId) =>
    store.getters['agentApplication/getAgent']?.id === agentId

  realtime.registerEvent('agent_chat_updated', ({ store }, { chat }) => {
    if (!isCurrentAgent(store, chat.agent_id)) {
      return
    }
    store.dispatch('agentHistory/forceUpdateChat', { chat })
    store.dispatch('agentChat/handleChatUpdated', { chat })
    // A finished triggered run moves the application's "last run".
    if (chat.source === 'trigger' && chat.completed_on) {
      const agent = store.getters['agentApplication/getAgent']
      const application = store.getters['application/get'](
        agent?.application_id
      )
      if (
        application !== undefined &&
        (!application.last_run_on ||
          new Date(chat.completed_on) > new Date(application.last_run_on))
      ) {
        store.dispatch('application/forceUpdate', {
          application,
          data: { last_run_on: chat.completed_on },
        })
      }
    }
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
    if (isCurrentAgent(store, agent.id)) {
      store.dispatch('agentApplication/forceUpdate', { values: agent })
    }
  })

  // The link rows are deleted with the skill; drop them from the open agent
  // so a later save does not resend a skill that no longer exists.
  realtime.registerEvent(
    'workspace_skill_deleted',
    ({ store }, { skill_id: skillId }) => {
      const agent = store.getters['agentApplication/getAgent']
      if (agent?.skills?.some((entry) => entry.skill_id === skillId)) {
        store.dispatch('agentApplication/forceUpdate', {
          values: {
            skills: agent.skills.filter((entry) => entry.skill_id !== skillId),
          },
        })
      }
    }
  )

  // Trigger, tool and channel changes arrive with the changed object, so the
  // stores apply them without refetching. The session that made the change
  // is left out by the backend, except for undo and redo.
  const isCurrentApplication = (store, applicationId) =>
    store.getters['agentApplication/getAgent']?.application_id === applicationId
  const configurationEvents = {
    agent_trigger_created: ['forceCreateTrigger', 'trigger'],
    agent_trigger_updated: ['forceUpdateTrigger', 'trigger'],
    agent_trigger_deleted: ['forceDeleteTrigger', 'trigger_id', 'triggerId'],
    agent_tool_created: ['forceCreateTool', 'tool'],
    agent_tool_updated: ['forceUpdateTool', 'tool'],
    agent_tool_deleted: ['forceDeleteTool', 'tool_id', 'toolId'],
    agent_chat_channel_created: ['forceCreateChannel', 'channel'],
    agent_chat_channel_updated: ['forceUpdateChannel', 'channel'],
    agent_chat_channel_deleted: [
      'forceDeleteChannel',
      'channel_id',
      'channelId',
    ],
  }
  Object.entries(configurationEvents).forEach(
    ([event, [action, payloadKey, argumentKey = payloadKey]]) => {
      realtime.registerEvent(event, ({ store }, payload) => {
        if (isCurrentApplication(store, payload.application_id)) {
          store.dispatch(`agentApplication/${action}`, {
            [argumentKey]: payload[payloadKey],
          })
        }
      })
    }
  )
}
