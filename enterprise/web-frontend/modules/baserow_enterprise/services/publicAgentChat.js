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
    /**
     * Repeating a start with the same key and content answers like the first
     * time, so a retry never starts a second conversation.
     *
     * @param {string} slug The slug of the public chat.
     * @param {object} values `{ key, content }`; the key is a secret the page
     *   generates, 32 to 128 lowercase hexadecimal digits or hyphens.
     * @param {string|null} token The access token of a protected chat.
     */
    startConversation(slug, values, token = null) {
      return client.post(
        `/agent/public-chat/${slug}/conversations/`,
        values,
        withToken(token)
      )
    },
    getConversation(slug, token) {
      return client.get(
        `/agent/public-chat/${slug}/conversation/`,
        withToken(token)
      )
    },
    /**
     * @param {string} slug The slug of the public chat.
     * @param {object} values `{ uuid, content }`; a repeat answers like the first.
     * @param {string} token The token of the visitor's conversation.
     */
    sendMessage(slug, values, token) {
      return client.post(
        `/agent/public-chat/${slug}/conversation/messages/`,
        values,
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
