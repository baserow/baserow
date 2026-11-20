/**
 * Signing in to a provider for an integration that connects an account. The
 * endpoints are the same for every such integration type.
 *
 * @param {Object} client The API client.
 * @param {string} integrationType The integration type, e.g. `microsoft`.
 */
export default (client, integrationType) => {
  const base = `/integrations/oauth/${encodeURIComponent(integrationType)}`
  return {
    getConfig() {
      return client.get(`${base}/config/`)
    },
    /**
     * @param {Object} target `{ applicationId }` to create an integration, or
     *   `{ integrationId }` to connect one again.
     * @param {string[]} serviceTypes What the account is connected for.
     * @param {string} name The name of the integration to create.
     */
    start({ applicationId = null, integrationId = null }, serviceTypes, name) {
      return client.post(`${base}/start/`, {
        application_id: applicationId,
        integration_id: integrationId,
        service_types: serviceTypes || [],
        name: name || '',
      })
    },
    complete({ state, code, error, errorDescription }) {
      return client.post(`${base}/complete/`, {
        state,
        code: code || '',
        error: error || '',
        error_description: errorDescription || '',
      })
    },
    disconnect(integrationId) {
      return client.post(`${base}/${integrationId}/disconnect/`)
    },
  }
}
