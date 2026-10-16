export default (client) => {
  return {
    async get(runId) {
      const { data } = await client.get(`/chat-runs/${runId}/`)
      return data
    },

    async cancel(runId) {
      const { data } = await client.post(`/chat-runs/${runId}/cancel/`)
      return data
    },
  }
}
