import { AGENT_APPLICATION_TYPE } from '@baserow/modules/agent/constants'

/** Hand a change to the open Agent page through its application. */
function notifyConversationChange(store, data, change) {
  const agent = store.getters['application/get'](data.agent_id)
  if (agent?.type !== AGENT_APPLICATION_TYPE) return

  // Conversations only: messages are read through the API.
  store.dispatch('application/forceUpdate', {
    application: agent,
    data: {
      _: {
        ...agent._,
        conversationUpdate: {
          version: (agent._.conversationUpdate?.version || 0) + 1,
          uuid: data.conversation_uuid,
          ...change,
        },
      },
    },
  })
}

/** Keep action configuration changes scoped to its application. */
function notifyActionChange(store, data, kind) {
  const agent = store.getters['application/get'](data.agent_id)
  if (agent?.type !== AGENT_APPLICATION_TYPE) return
  store.dispatch('application/forceUpdate', {
    application: agent,
    data: {
      _: {
        ...agent._,
        actionUpdate: {
          version: (agent._.actionUpdate?.version || 0) + 1,
          kind,
          action: data.action,
          actionId: data.action_id,
        },
      },
    },
  })
}

export const registerRealtimeEvents = (realtime) => {
  for (const kind of ['created', 'updated', 'deleted']) {
    realtime.registerEvent(`agent_action_${kind}`, ({ store }, data) =>
      notifyActionChange(store, data, kind)
    )
  }
  realtime.registerEvent('agent_conversation_activity', ({ store }, data) =>
    notifyConversationChange(store, data, {
      kind: 'activity',
      conversation: data.conversation,
    })
  )
  realtime.registerEvent('agent_conversation_updated', ({ store }, data) =>
    notifyConversationChange(store, data, {
      kind: 'updated',
      values: data.values,
      conversation: data.conversation,
    })
  )
  realtime.registerEvent('agent_conversation_deleted', ({ store }, data) =>
    notifyConversationChange(store, data, { kind: 'deleted' })
  )
}
