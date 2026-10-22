import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'

import SubjectRoleAssignmentRows from '@baserow_enterprise/components/member-roles/SubjectRoleAssignmentRows'
import { EnterpriseRolesAgentExtensionType } from '@baserow_enterprise/agentExtensionTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import { EnterpriseMembersPagePluginType } from '@baserow_enterprise/membersPagePluginTypes'
import { getSubjectRoleAssignmentsRowExpansion } from '@baserow_enterprise/utils/subjectRoleAssignments'

const roles = [
  { uid: 'ADMIN', name: 'Admin', isVisible: true },
  { uid: 'BUILDER', name: 'Builder', isVisible: true },
  { uid: 'EDITOR', name: 'Editor', isVisible: true },
  { uid: 'NO_ACCESS', name: 'No access', isVisible: true },
]
const workspace = { id: 12, name: 'Widelab', _: { roles } }
const columns = [
  { key: 'name' },
  { key: 'email' },
  { key: 'role_uid' },
  { key: 'teams' },
  { key: null, stickyRight: true },
]
const projects = { scope_type: 'application', scope_id: 30, name: 'Projects' }
const tasks = { scope_type: 'database_table', scope_id: 20, name: 'Tasks' }
const roleAssignment = (overrides) => ({
  type: null,
  parents: [],
  role: 'BUILDER',
  locked_by: null,
  ...overrides,
})
const firstPage = [
  roleAssignment({ ...projects, type: 'database' }),
  roleAssignment({ ...tasks, parents: [projects] }),
  roleAssignment({
    scope_type: 'database_view',
    scope_id: 40,
    name: 'Kanban - Q3',
    type: 'kanban',
    parents: [projects, tasks],
    role: 'EDITOR',
  }),
]
// The answer the no access confirmation gives, and what it was asked.
const noAccessModal = { answer: true, asked: [] }

// Answers every request with the next page.
function createClient(pages = [firstPage], count = firstPage.length) {
  let page = 0
  return {
    get: vi.fn(() =>
      Promise.resolve({ data: { count, results: pages[page++] || [] } })
    ),
    post: vi.fn().mockResolvedValue({}),
  }
}

async function mountRows(
  client,
  { readOnly = false, canManage = true, row = { id: 3 } } = {}
) {
  noAccessModal.answer = true
  noAccessModal.asked = []
  const updateRow = vi.fn((values) => Object.assign(row, values))
  const wrapper = await mountSuspended(SubjectRoleAssignmentRows, {
    props: {
      workspace,
      row,
      columns,
      updateRow,
      subjectType: 'auth.User',
      subjectId: 8,
      roleColumnKey: 'role_uid',
      readOnly,
    },
    global: {
      mocks: {
        $client: client,
        $hasPermission: () => canManage,
        $registry: {
          get: (namespace, type) =>
            ({
              'application:database': {
                getName: () => 'Database',
                iconClass: 'iconoir-db',
              },
              'view:kanban': { iconClass: 'baserow-icon-kanban' },
            })[`${namespace}:${type}`],
        },
        $t: (key, params = {}) =>
          ({
            'subjectRoleAssignments.location': `${params.type} in ${params.path}`,
            'subjectRoleAssignments.table': 'Table',
            'subjectRoleAssignments.view': 'View',
            'subjectRoleAssignments.showMore': `Show ${params.count} more`,
            'common.workspace': 'Workspace',
            'shareScope.inheritedAdminHelpText': `Admin of the ${params.level}, ${params.type}`,
          })[key] || key,
      },
      stubs: {
        EditRoleContext: {
          template: '<div />',
          methods: { toggle() {}, hide() {} },
        },
        ScopeNoAccessModal: {
          template: '<div />',
          methods: {
            ask(description) {
              noAccessModal.asked.push(description)
              return Promise.resolve(noAccessModal.answer)
            },
          },
        },
        HelpIcon: {
          props: ['tooltip'],
          template: '<i class="help">{{ tooltip }}</i>',
        },
      },
    },
  })
  await flushPromises()
  return { wrapper, updateRow, row }
}

const rowTexts = (wrapper) =>
  wrapper
    .findAll('.subject-role-assignments__row')
    .map((row) =>
      [
        row.find('.subject-role-assignments__name').text(),
        row.find('.subject-role-assignments__location').text(),
        row.find('button').text(),
      ].join(' | ')
    )

test('lists the roles with where their objects are', async () => {
  const client = createClient()
  const { wrapper } = await mountRows(client)
  try {
    expect(client.get).toHaveBeenCalledWith(
      '/role/12/subject-role-assignments/',
      {
        params: {
          subject_type: 'auth.User',
          subject_id: 8,
          offset: 0,
          limit: 10,
        },
      }
    )
    expect(rowTexts(wrapper)).toEqual([
      'Projects | Database in Widelab | Builder',
      'Tasks | Table in Projects | Builder',
      'Kanban - Q3 | View in Projects / Tasks | Editor',
    ])
    expect(wrapper.find('.subject-role-assignments__more').exists()).toBe(false)
  } finally {
    wrapper.unmount()
  }
})

test('shows more roles a page at a time', async () => {
  const secondPage = [roleAssignment({ ...tasks, scope_id: 21, name: 'Notes' })]
  const client = createClient([firstPage, secondPage], 11)
  const { wrapper } = await mountRows(client)
  try {
    expect(wrapper.find('.subject-role-assignments__more').text()).toBe(
      'Show 8 more'
    )
    await wrapper.find('.subject-role-assignments__more').trigger('click')
    await flushPromises()
    expect(client.get).toHaveBeenLastCalledWith(
      '/role/12/subject-role-assignments/',
      {
        params: {
          subject_type: 'auth.User',
          subject_id: 8,
          offset: 3,
          limit: 10,
        },
      }
    )
    expect(wrapper.findAll('.subject-role-assignments__row')).toHaveLength(4)
  } finally {
    wrapper.unmount()
  }
})

test('shows a role inside an admin role as a locked admin role', async () => {
  const client = createClient(
    [
      [
        roleAssignment({
          ...tasks,
          parents: [projects],
          role: 'NO_ACCESS',
          locked_by: { scope_type: 'workspace', scope_id: 12, name: 'Widelab' },
        }),
      ],
    ],
    1
  )
  const { wrapper } = await mountRows(client)
  try {
    const row = wrapper.find('.subject-role-assignments__row')
    expect(row.find('button').text()).toBe('Admin')
    expect(row.find('button').element.disabled).toBe(true)
    expect(row.find('.help').text()).toBe('Admin of the workspace, table')
    expect(row.find('.subject-role-assignments__remove').exists()).toBe(true)
  } finally {
    wrapper.unmount()
  }
})

test('offers no changes for read only roles or without permission', async () => {
  for (const options of [{ readOnly: true }, { canManage: false }]) {
    const { wrapper } = await mountRows(createClient(), options)
    try {
      expect(wrapper.find('.subject-role-assignments__remove').exists()).toBe(
        false
      )
      expect(
        wrapper
          .findAll('.subject-role-assignments__row button')
          .every((button) => button.element.disabled)
      ).toBe(true)
    } finally {
      wrapper.unmount()
    }
  }
})

test('removes a role and updates the count of the row', async () => {
  const client = createClient()
  const { wrapper, updateRow } = await mountRows(client, {
    row: { id: 3, role_assignment_count: 3 },
  })
  try {
    await wrapper
      .findAll('.subject-role-assignments__remove')[1]
      .trigger('click')
    await flushPromises()
    expect(client.post).toHaveBeenCalledWith('/role/12/', {
      subject_id: 8,
      subject_type: 'auth.User',
      scope_id: 20,
      scope_type: 'database_table',
      role: null,
    })
    expect(rowTexts(wrapper)).toHaveLength(2)
    expect(updateRow).toHaveBeenLastCalledWith(
      expect.objectContaining({ id: 3, role_assignment_count: 2 })
    )
  } finally {
    wrapper.unmount()
  }
})

test('asks before giving no access, and restores a role that failed to change', async () => {
  const client = createClient()
  const { wrapper } = await mountRows(client)
  const item = () => wrapper.vm.items[0]
  try {
    noAccessModal.answer = false
    await wrapper.vm.changeRole(item(), 'NO_ACCESS')
    expect(noAccessModal.asked).toEqual(['shareScope.noAccessDescription'])
    expect(client.post).not.toHaveBeenCalled()

    const notify = vi.fn()
    client.post.mockRejectedValueOnce({ handler: { notifyIf: notify } })
    await wrapper.vm.changeRole(item(), 'EDITOR')
    await flushPromises()
    expect(client.post).toHaveBeenCalledTimes(1)
    expect(notify).toHaveBeenCalled()
    expect(item().roleUid).toBe('BUILDER')
  } finally {
    wrapper.unmount()
  }
})

test('expands rows with roles only, labelled with their count', () => {
  const expansion = getSubjectRoleAssignmentsRowExpansion({
    subjectType: 'auth.User',
    columnKey: 'role_uid',
    getSubjectId: (row) => row.user_id,
    isReadOnly: (row) => row.user_id === 7,
  })
  expect(expansion.isExpandable({ role_assignment_count: 0 })).toBe(false)
  expect(expansion.isExpandable({})).toBe(false)
  expect(expansion.isExpandable({ role_assignment_count: 2 })).toBe(true)
  expect(expansion.getToggleLabel({ role_assignment_count: 2 })).toBe('+2')
  expect(expansion.getProps({ id: 1, user_id: 7 })).toEqual({
    subjectType: 'auth.User',
    subjectId: 7,
    roleColumnKey: 'role_uid',
    readOnly: true,
  })
})

test('reloads the roles when the workspace role of the subject changes', async () => {
  const locked = firstPage.map((item) => ({
    ...item,
    locked_by: { scope_type: 'workspace', scope_id: 12, name: 'Widelab' },
  }))
  const client = createClient([firstPage, locked])
  const { wrapper } = await mountRows(client, {
    row: { id: 3, role_uid: 'EDITOR' },
  })
  try {
    await wrapper.setProps({ row: { id: 3, role_uid: 'ADMIN' } })
    await flushPromises()
    expect(client.get).toHaveBeenLastCalledWith(
      '/role/12/subject-role-assignments/',
      {
        params: {
          subject_type: 'auth.User',
          subject_id: 8,
          offset: 0,
          limit: 10,
        },
      }
    )
    expect(
      wrapper
        .findAll('.subject-role-assignments__role button')
        .map((button) => button.text())
    ).toEqual(['Admin', 'Admin', 'Admin'])
  } finally {
    wrapper.unmount()
  }
})

test('members and agents offer their roles as row expansions', () => {
  const app = {
    $store: { getters: { 'auth/getUserId': 7 } },
    $hasFeature: (feature) => feature === EnterpriseFeatures.RBAC,
  }

  const members = new EnterpriseMembersPagePluginType({ app }).getRowExpansion()
  expect(members.columnKey).toBe('role_uid')
  // Nobody can change their own roles.
  expect(members.getProps({ id: 1, user_id: 7 })).toMatchObject({
    subjectType: 'auth.User',
    subjectId: 7,
    readOnly: true,
  })
  expect(members.getProps({ id: 2, user_id: 8 }).readOnly).toBe(false)

  const agents = new EnterpriseRolesAgentExtensionType({ app })
  expect(agents.isActive({ id: 12 })).toBe(true)
  expect(agents.getRowExpansion().getProps({ id: 5 })).toEqual({
    subjectType: 'core.Agent',
    subjectId: 5,
    roleColumnKey: 'role_uid',
    readOnly: false,
  })
  const withoutRbac = new EnterpriseRolesAgentExtensionType({
    app: { ...app, $hasFeature: () => false },
  })
  expect(withoutRbac.isActive({ id: 12 })).toBe(false)
})
