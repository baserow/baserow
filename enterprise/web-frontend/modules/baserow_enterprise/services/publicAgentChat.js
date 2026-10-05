/**
 * The public web chat endpoints. They need no Baserow account; a password
 * protected chat sends its access token in the `Baserow-Agent-Chat-Authorization`
 * header.
 */
const base = (slug) => `/agent_application/public/chat/${slug}/`

const withToken = (token) =>
  token
    ? { headers: { 'Baserow-Agent-Chat-Authorization': `JWT ${token}` } }
    : {}

export default (client) => {
  return {
    get(slug, token) {
      return client.get(base(slug), withToken(token))
    },
    auth(slug, password) {
      return client.post(`${base(slug)}auth/`, { password })
    },
    createConversation(slug, token) {
      return client.post(`${base(slug)}conversations/`, null, withToken(token))
    },
    getConversation(slug, uuid, token) {
      return client.get(`${base(slug)}conversations/${uuid}/`, withToken(token))
    },
    sendMessage(slug, uuid, content, token) {
      return client.post(
        `${base(slug)}conversations/${uuid}/messages/`,
        { content },
        withToken(token)
      )
    },
  }
}
