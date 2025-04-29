/**
 * Registers the real time events related to the baserow_enterprise module. When a message
 * comes in, the state of the stores will be updated to match the latest update.
 */

export const registerRealtimeEvents = (realtime) => {
  realtime.registerEvent(
    'permissions_updated',
    async ({ store }, { workspace_id: workspaceId }) => {
      const workspace = store.getters['workspace/get'](workspaceId)
      if (workspace) {
        try {
          await store.dispatch('workspace/forceFetchPermissions', workspace)
        } catch (e) {
          await store.dispatch('toast/setPermissionsUpdated', true)
        }
      }
    }
  )
}
