export default (client) => {
  return {
    authorize(integrationId, returnUrl) {
      return client.post(`integration/${integrationId}/oauth2/authorize/`, {
        return_url: returnUrl,
      })
    },
  }
}
