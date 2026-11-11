import { createStreamAdapter } from '@baserow/modules/core/chatRuns/stream'

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

    /**
     * Reads a run's records after a cursor as they arrive, until the run ends.
     *
     * @param {string} runId The id of the run.
     * @param {string|null} cursor The cursor of the last record received, or
     *   null to read from the start.
     * @param {Function} onRecord Called with each record, in order.
     * @param {AbortSignal} [signal] Aborting closes the response; the run
     *   continues.
     * @returns {Promise<object>} Resolves once every record has been handled.
     */
    stream(runId, cursor, onRecord, signal) {
      return client.get(`/chat-runs/${runId}/stream/`, {
        params: { cursor },
        adapter: createStreamAdapter(onRecord, signal),
      })
    },
  }
}
