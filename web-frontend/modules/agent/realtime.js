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

export const registerRealtimeEvents = (realtime) => {
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
    })
  )
  realtime.registerEvent('agent_conversation_deleted', ({ store }, data) =>
    notifyConversationChange(store, data, { kind: 'deleted' })
  )
}
