/** The team, channel and chat pickers of the Teams actions. */
export default (client) => ({
  listTeams(integrationId) {
    return client.get(`/integrations/microsoft-teams/${integrationId}/teams/`)
  },
  listChannels(integrationId, teamId) {
    return client.get(
      `/integrations/microsoft-teams/${integrationId}/teams/${encodeURIComponent(
        teamId
      )}/channels/`
    )
  },
  listChats(integrationId) {
    return client.get(`/integrations/microsoft-teams/${integrationId}/chats/`)
  },
})
