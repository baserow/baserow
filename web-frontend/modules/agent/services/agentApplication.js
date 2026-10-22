import { getRealtimeRecoveryRequestConfig } from '@baserow/modules/core/plugins/realtimeProtocol'

const CONVERSATION_PAGE_SIZE = 20
const MESSAGE_PAGE_SIZE = 50

export default (client) => ({
  get(agentId) {
    return client.get(`/agent/${agentId}/`)
  },
  recordView(agentId) {
    return client.post(`/agent/${agentId}/`)
  },
  getConfiguration(agentId) {
    return client.get(`/agent/${agentId}/configuration/`)
  },
  updateConfiguration(agentId, values) {
    return client.patch(`/agent/${agentId}/configuration/`, values)
  },
  getConversations(agentId, page = 1) {
    return client.get(`/agent/${agentId}/conversations/`, {
      params: { page, size: CONVERSATION_PAGE_SIZE },
    })
  },
  createConversation(agentId, values) {
    return client.post(`/agent/${agentId}/conversations/`, values)
  },
  getMessages(agentId, conversationUuid, page = 1, realtimeRecovery = false) {
    return client.get(
      `/agent/${agentId}/conversations/${conversationUuid}/messages/`,
      {
        params: { page, size: MESSAGE_PAGE_SIZE },
        ...(realtimeRecovery ? getRealtimeRecoveryRequestConfig() : {}),
      }
    )
  },
  createMessage(agentId, conversationUuid, values) {
    return client.post(
      `/agent/${agentId}/conversations/${conversationUuid}/messages/`,
      values
    )
  },
})
