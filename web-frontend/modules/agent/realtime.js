export const registerRealtimeEvents = (realtime) => {
  realtime.registerEvent('agent_conversation_updated', ({ store }, data) => {
    const agent = store.getters['application/get'](data.agent_id)
    if (agent?.type !== 'agent') return

    // Only invalidation metadata enters the application store. Private content
    // is fetched through the permission-checked API by the open Agent page.
    store.dispatch('application/forceUpdate', {
      application: agent,
      data: {
        _: {
          ...agent._,
          conversationUpdate: {
            version: (agent._.conversationUpdate?.version || 0) + 1,
            uuid: data.conversation_uuid,
            runId: data.run_id,
            updatedOn: data.updated_on,
          },
        },
      },
    })
  })
}
