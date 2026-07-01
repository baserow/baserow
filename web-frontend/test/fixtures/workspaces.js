export function createWorkspace(mock, { workspaceId = 1 }) {
  const workspace = {
    order: workspaceId,
    permissions: 'ADMIN',
    id: workspaceId,
    name: `workspace_${workspaceId}`,
    users: [],
  }
  mock.onGet('/workspaces/').reply(200, [workspace])
  return workspace
}
