export default (client) => {
  return {
    getApplicationOverview(applicationId) {
      return client.get(`/automatic-snapshots/application/${applicationId}/`)
    },
    createApplicationSchedule(applicationId, values) {
      return client.post(
        `/automatic-snapshots/application/${applicationId}/`,
        values
      )
    },
    updateApplicationSchedule(applicationId, values) {
      return client.patch(
        `/automatic-snapshots/application/${applicationId}/`,
        values
      )
    },
    deleteApplicationSchedule(applicationId) {
      return client.delete(`/automatic-snapshots/application/${applicationId}/`)
    },
    getWorkspaceSchedules(workspaceId) {
      return client.get(`/automatic-snapshots/workspace/${workspaceId}/`)
    },
    createWorkspaceDefault(workspaceId, values) {
      return client.post(
        `/automatic-snapshots/workspace/${workspaceId}/`,
        values
      )
    },
    updateWorkspaceDefault(workspaceId, values) {
      return client.patch(
        `/automatic-snapshots/workspace/${workspaceId}/`,
        values
      )
    },
    deleteWorkspaceDefault(workspaceId) {
      return client.delete(`/automatic-snapshots/workspace/${workspaceId}/`)
    },
    bulkUpdate(workspaceId, values) {
      return client.post(
        `/automatic-snapshots/workspace/${workspaceId}/bulk/`,
        values
      )
    },
  }
}
