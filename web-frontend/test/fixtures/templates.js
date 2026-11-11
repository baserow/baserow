// An official template whose workspace holds two databases.
export const template = {
  id: 5,
  slug: 'project-tracker',
  name: 'Project Tracker',
  workspace_id: 10,
  open_application: null,
}

const database = (id, name, order) => ({
  id,
  name,
  order,
  type: 'database',
  workspace: { id: template.workspace_id },
  tables: [{ id: id * 10, name: `${name} table`, order: 1, database_id: id }],
})

/**
 * Answers the applications of the template workspace out of order, so that the
 * sidebar must sort them by `order`: 'First' with the 'First table', then
 * 'Second' with the 'Second table'.
 */
export function mockTemplateApplications(mock) {
  mock
    .onGet(`/applications/workspace/${template.workspace_id}/`)
    .reply(200, [database(1, 'Second', 2), database(2, 'First', 1)])
}
