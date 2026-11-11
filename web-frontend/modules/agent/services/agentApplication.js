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
  getConfiguration(agentId, realtimeRecovery = false) {
    return client.get(`/agent/${agentId}/configuration/`, {
      ...(realtimeRecovery ? getRealtimeRecoveryRequestConfig() : {}),
    })
  },
  getRunAsSubjects(agentId, page = 1, search = '') {
    return client.get(`/agent/${agentId}/run-as-subjects/`, {
      params: { page, search, size: 100 },
      // Opening the picker revalidates choices, including changes missed while
      // disconnected. A lagging replica must not reintroduce a deleted choice.
      ...getRealtimeRecoveryRequestConfig(),
    })
  },
  updateConfiguration(agentId, { run_as: runAs, ...values }) {
    if (runAs !== undefined) {
      values.run_as_subject_type = runAs?.type ?? null
      values.run_as_subject_id = runAs?.id ?? null
    }
    return client.patch(`/agent/${agentId}/configuration/`, values)
  },
  getConversations(
    agentId,
    cursor = null,
    { realtimeRecovery = false, ...filters } = {}
  ) {
    return client.get(`/agent/${agentId}/conversations/`, {
      params: {
        cursor,
        limit: CONVERSATION_PAGE_SIZE,
        ...filters,
      },
      ...(realtimeRecovery ? getRealtimeRecoveryRequestConfig() : {}),
    })
  },
  createConversation(agentId, values) {
    return client.post(`/agent/${agentId}/conversations/`, values)
  },
  updateConversation(agentId, conversationUuid, values) {
    return client.patch(
      `/agent/${agentId}/conversations/${conversationUuid}/`,
      values
    )
  },
  deleteConversation(agentId, conversationUuid) {
    return client.delete(`/agent/${agentId}/conversations/${conversationUuid}/`)
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
  decideApprovals(agentId, conversationUuid, decisions, { alwaysAllow } = {}) {
    return client.post(
      `/agent/${agentId}/conversations/${conversationUuid}/approvals/`,
      { decisions, ...(alwaysAllow ? { always_allow: true } : {}) }
    )
  },
})
