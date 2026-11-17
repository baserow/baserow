export default (client) => {
  return {
    list(applicationId) {
      return client.get(`/snapshots/application/${applicationId}/`)
    },
    usage(applicationId) {
      return client.get(`/snapshots/application/${applicationId}/usage/`)
    },
    create(applicationId, values) {
      return client.post(`/snapshots/application/${applicationId}/`, values)
    },
    restore(snapshotId) {
      return client.post(`/snapshots/${snapshotId}/restore/`)
    },
    delete(snapshotId) {
      return client.delete(`/snapshots/${snapshotId}/`)
    },
    updateProtected(snapshotId, isProtected) {
      return client.patch(`/snapshots/${snapshotId}/`, {
        protected: isProtected,
      })
    },
    /**
     * Changes how many snapshots the application keeps. A `null` keep makes it
     * follow the workspace default keep again.
     */
    updateKeep(applicationId, keep, deleteSnapshots = false) {
      return client.patch(`/snapshots/application/${applicationId}/keep/`, {
        keep,
        delete_snapshots: deleteSnapshots,
      })
    },
    getWorkspaceSettings(workspaceId) {
      return client.get(`/snapshots/workspace/${workspaceId}/`)
    },
    updateWorkspaceDefaultKeep(
      workspaceId,
      defaultKeep,
      deleteSnapshots = false
    ) {
      return client.patch(`/snapshots/workspace/${workspaceId}/`, {
        default_keep: defaultKeep,
        delete_snapshots: deleteSnapshots,
      })
    },
  }
}
