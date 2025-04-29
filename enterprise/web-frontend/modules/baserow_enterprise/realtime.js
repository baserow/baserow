/**
 * Registers the real time events related to the baserow_enterprise module. When a message
 * comes in, the state of the stores will be updated to match the latest update.
 */

export const registerRealtimeEvents = (realtime) => {
  const updateWorkspacePermissions = async (store, workspaceId) => {
    const workspace = store.getters['workspace/get'](workspaceId)
    if (workspace) {
      try {
        await store.dispatch('workspace/forceFetchPermissions', workspace)
      } catch (e) {
        await store.dispatch('toast/setPermissionsUpdated', true)
      }
    }
  }

  realtime.registerEvent(
    'permissions_updated',
    ({ store }, { workspace_id: workspaceId }) => {
      updateWorkspacePermissions(store, workspaceId)
    }
  )

  realtime.registerEvent(
    'field_permissions_updated',
    ({ store, app }, payload) => {
      const {
        workspace_id: workspaceId,
        field_id: fieldId,
        role,
        allow_in_forms: allowInForms,
      } = payload

      app.$bus.$emit('field-permissions-updated', {
        fieldId,
        role,
        allowInForms,
      })

      updateWorkspacePermissions(store, workspaceId)
    }
  )
}
