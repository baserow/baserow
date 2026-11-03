import { AGENT_APPLICATION_TYPE } from '@baserow/modules/agent/constants'

/** Hand a change to the open Agent page through its application. */
function notifyConversationChange(store, data, change) {
  const agent = store.getters['application/get'](data.agent_id)
  if (agent?.type !== AGENT_APPLICATION_TYPE) return

  // Titles and run metadata only: messages are read through the permission-checked API.
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
  realtime.registerEvent('agent_conversation_updated', ({ store }, data) =>
    notifyConversationChange(store, data, {
      runId: data.run_id,
      updatedOn: data.updated_on,
    })
  )
  realtime.registerEvent('agent_conversation_renamed', ({ store }, data) =>
    notifyConversationChange(store, data, { title: data.title })
  )
  realtime.registerEvent('agent_conversation_deleted', ({ store }, data) =>
    notifyConversationChange(store, data, { deleted: true })
  )
}
