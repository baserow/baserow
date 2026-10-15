import { mountSuspended } from '@nuxt/test-utils/runtime'
import { expect, test } from 'vitest'

import MemberRolesTab from '@baserow_enterprise/components/member-roles/MemberRolesTab'

const ListProbe = {
  props: ['inheritedAdmins', 'scopeTypeName'],
  template:
    '<div class="list" :data-scope-type-name="scopeTypeName">{{ JSON.stringify(inheritedAdmins) }}</div>',
}

const PickerProbe = {
  props: ['users', 'teams', 'agents'],
  template:
    '<div class="picker" :data-users="users.map((user) => user.user_id).join()" :data-teams="teams.map((team) => team.id).join()" :data-agents="agents.map((agent) => agent.id).join()" />',
}

test('locks admins of the workspace and of the database and keeps them out of the picker', async () => {
  const wrapper = await mountSuspended(MemberRolesTab, {
    props: {
      workspace: {
        id: 1,
        name: 'Acme',
        users: [
          { user_id: 1, name: 'Me', email: 'me@acme.io', permissions: 'ADMIN' },
          {
            user_id: 2,
            name: 'Bob',
            email: 'bob@acme.io',
            permissions: 'ADMIN',
          },
          {
            user_id: 3,
            name: 'Carol',
            email: 'carol@acme.io',
            permissions: 'MEMBER',
          },
          {
            user_id: 4,
            name: 'Dan',
            email: 'dan@acme.io',
            permissions: 'MEMBER',
          },
        ],
      },
      scope: { id: 5, name: 'People' },
      scopeType: 'database_table',
      roleAssignments: [
        { subject_type: 'auth.User', subject: { id: 2 }, role: 'NO_ACCESS' },
      ],
      teams: [
        { id: 9, name: 'Sales', subject_count: 1 },
        { id: 10, name: 'Ops', subject_count: 2 },
      ],
      agents: [
        { id: 7, name: 'Bot', role_uid: 'ADMIN' },
        { id: 8, name: 'Helper', role_uid: 'BUILDER' },
      ],
      ancestorAdmins: { 'auth.User:4': 'database' },
    },
    global: {
      mocks: {
        $store: { getters: { 'auth/getUserId': 1 } },
      },
      stubs: {
        MemberRolesMembersList: ListProbe,
        RoleAssignmentModal: PickerProbe,
        HelpIcon: true,
        Button: true,
        Alert: { template: '<div><slot /></div>' },
      },
    },
  })

  const list = wrapper.find('.list')
  expect(JSON.parse(list.text())).toStrictEqual({
    'auth.User:4': 'database',
    'auth.User:1': 'common.workspace',
    'auth.User:2': 'common.workspace',
    'core.Agent:7': 'common.workspace',
  })
  expect(list.attributes('data-scope-type-name')).toBe('trashtype.table')

  // Neither the current user, nor Bob who already has a role here, nor the
  // admins can be picked. Teams always can: their roles never lock anyone.
  const picker = wrapper.find('.picker')
  expect(picker.attributes('data-users')).toBe('3')
  expect(picker.attributes('data-teams')).toBe('9,10')
  expect(picker.attributes('data-agents')).toBe('8')
})
