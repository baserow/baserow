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
