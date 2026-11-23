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
     * Changes how many snapshots the application keeps. A `null` max snapshots makes it
     * follow the workspace default max snapshots again.
     */
    updateMaxSnapshots(applicationId, maxSnapshots, deleteSnapshots = false) {
      return client.patch(
        `/snapshots/application/${applicationId}/max-snapshots/`,
        {
          max_snapshots: maxSnapshots,
          delete_snapshots: deleteSnapshots,
        }
      )
    },
    getWorkspaceSettings(workspaceId) {
      return client.get(`/snapshots/workspace/${workspaceId}/`)
    },
    updateWorkspaceDefaultMaxSnapshots(
      workspaceId,
      defaultMaxSnapshots,
      deleteSnapshots = false
    ) {
      return client.patch(`/snapshots/workspace/${workspaceId}/`, {
        default_max_snapshots: defaultMaxSnapshots,
        delete_snapshots: deleteSnapshots,
      })
    },
  }
}
