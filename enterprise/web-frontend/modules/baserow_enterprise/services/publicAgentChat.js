import { createStreamAdapter } from '@baserow/modules/core/chatRuns/stream'

export const PUBLIC_AGENT_CHAT_AUTHORIZATION_HEADER =
  'Baserow-Agent-Chat-Authorization'

const withToken = (token) =>
  token
    ? { headers: { [PUBLIC_AGENT_CHAT_AUTHORIZATION_HEADER]: `JWT ${token}` } }
    : {}

/**
 * The anonymous endpoints of a public chat, addressed by its slug. The token is
 * the access token of a password protected chat or the token of the visitor's
 * conversation.
 */
export default (client) => {
  return {
    getInfo(slug, token = null) {
      return client.get(`/agent/public-chat/${slug}/`, withToken(token))
    },
    authorize(slug, password) {
      return client.post(`/agent/public-chat/${slug}/auth/`, { password })
    },
    startConversation(slug, content, token = null) {
      return client.post(
        `/agent/public-chat/${slug}/conversations/`,
        { content },
        withToken(token)
      )
    },
    getConversation(slug, token) {
      return client.get(
        `/agent/public-chat/${slug}/conversation/`,
        withToken(token)
      )
    },
    sendMessage(slug, content, token) {
      return client.post(
        `/agent/public-chat/${slug}/conversation/messages/`,
        { content },
        withToken(token)
      )
    },
    stop(slug, token) {
      return client.post(
        `/agent/public-chat/${slug}/conversation/stop/`,
        null,
        withToken(token)
      )
    },
    /**
     * Reads the records of the run writing a reply as they arrive, until it ends.
     *
     * @param {string} slug The slug of the public chat.
     * @param {string} runId The run writing the reply.
     * @param {string|null} cursor The cursor of the last record received, or
     *   null to read from the start.
     * @param {string} token The token of the visitor's conversation.
     * @param {Function} onRecord Called with each record, in order.
     * @param {AbortSignal} signal Aborting closes the response; the run continues.
     * @returns {Promise<object>} Resolves once every record has been handled.
     */
    stream(slug, runId, cursor, token, onRecord, signal) {
      return client.get(`/chat-runs/agent-public-chat/${slug}/stream/`, {
        ...withToken(token),
        params: { run_id: runId, cursor },
        adapter: createStreamAdapter(onRecord, signal),
      })
    },
  }
}
