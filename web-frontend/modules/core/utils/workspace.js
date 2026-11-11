import { ConcurrentPriorityTaskQueue } from '@baserow/modules/core/utils/queue'

export const getWorkspaceMembersCount = (workspace, canListAgents) =>
  (workspace.users?.length || 0) +
  (canListAgents ? workspace.agents_count || 0 : 0)

/**
 * Fetches the workspaces and applications of the authenticated user if that hasn't
 * happened yet, and selects the provided workspace if it exists. Shared by the
 * `workspacesAndApplications` middleware and the pages that fetch them without
 * blocking the navigation, so that the workspace of the route is selected
 * regardless of which page loaded them first.
 */
export const fetchWorkspacesAndApplications = async (nuxtApp, workspaceId) => {
  const store = nuxtApp.$store

  if (!store.getters['workspace/isLoaded']) {
    await store.dispatch('workspace/fetchAll')

    const workspaces = store.getters['workspace/getAll']
    const workspaceExists =
      workspaces.find((w) => w.id === workspaceId) !== undefined

    if (workspaceExists) {
      try {
        await store.dispatch('workspace/selectById', workspaceId)
      } catch {}
    }
  }

  if (!store.getters['application/isLoaded']) {
    await store.dispatch('application/fetchAll')
  }
}

// A burst of requests hits the concurrency limit of the API, so the permissions
// of many workspaces are fetched a few at a time.
const permissionsQueue = new ConcurrentPriorityTaskQueue({ concurrency: 3 })

/**
 * Fetches the permissions of the workspaces that don't have them yet. A failure
 * is ignored, so that the global permissions are used for that workspace and the
 * backend checks again.
 */
export const fetchPermissionsOfWorkspaces = (store, workspaces) =>
  Promise.all(
    workspaces
      .filter((workspace) => !workspace._.permissionsLoaded)
      .map((workspace) =>
        permissionsQueue
          .add(() => store.dispatch('workspace/fetchPermissions', workspace))
          .catch(() => {})
      )
  )
