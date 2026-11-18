import ApplicationService from '@baserow/modules/core/services/application'

async function refreshWorkspaceAccess(store, workspace) {
  const { data: applications } = await ApplicationService(
    store.$client
  ).fetchAll(workspace.id)
  const visibleIds = new Set(applications.map(({ id }) => id))
  for (const existing of store.getters['application/getAllOfWorkspace'](
    workspace
  )) {
    if (!visibleIds.has(existing.id)) {
      await store.dispatch('application/forceDelete', existing)
    }
  }
  for (const application of applications) {
    const existing = store.getters['application/get'](application.id)
    if (!existing) {
      await store.dispatch('application/forceCreate', application)
    } else if (application.type === 'database') {
      // A table grant can change while the database itself remains visible.
      const visibleTables = new Set(application.tables.map(({ id }) => id))
      for (const table of existing.tables.filter(
        ({ id }) => !visibleTables.has(id)
      )) {
        await store.dispatch('table/forceDelete', { database: existing, table })
      }
      for (const table of application.tables) {
        await store.dispatch('table/forceUpsert', {
          database: existing,
          data: table,
        })
      }
    }
  }
}

/**
 * Registers the real time events related to the baserow_enterprise module. When a message
 * comes in, the state of the stores will be updated to match the latest update.
 */

export const registerRealtimeEvents = (realtime) => {
  const updateWorkspacePermissions = async (
    store,
    workspaceId,
    refreshApplications = false
  ) => {
    const workspace = store.getters['workspace/get'](workspaceId)
    if (workspace) {
      try {
        await store.dispatch('workspace/forceFetchPermissions', workspace)
        if (refreshApplications) {
          await refreshWorkspaceAccess(store, workspace)
        }
      } catch (e) {
        await store.dispatch('toast/setPermissionsUpdated', true)
      }
    }
  }

  // A slower grant response must finish before applying a later revocation.
  let roleRefresh = Promise.resolve()
  realtime.registerEvent(
    'permissions_updated',
    ({ store }, { workspace_id: workspaceId }) => {
      const refresh = () => updateWorkspacePermissions(store, workspaceId, true)
      roleRefresh = roleRefresh.then(refresh, refresh)
      return roleRefresh
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

  realtime.registerEvent(
    'semantic_search_field_status_updated',
    ({ store }, { field_id: fieldId, semantic_search_status: status }) => {
      store.commit('field/SET_ITEM_VALUES', {
        id: fieldId,
        values: { semantic_search_status: status },
      })
    }
  )
}
