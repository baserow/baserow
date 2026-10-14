import { mountSuspended } from '@nuxt/test-utils/runtime'

import MemberRolesMembersList from '@baserow_enterprise/components/member-roles/MemberRolesMembersList'

const RoleSelectorStub = {
  props: {
    disabled: Boolean,
  },
  template: '<button class="role-selector" :disabled="disabled" />',
}

describe('MemberRolesMembersList', () => {
  test('renders registered subject names and avatar colors', async () => {
    const wrapper = await mountSuspended(MemberRolesMembersList, {
      props: {
        roleAssignments: [
          {
            subject_type: 'auth.User',
            subject: { id: 1, first_name: 'Ada' },
            role: 'MEMBER',
          },
          {
            subject_type: 'core.Agent',
            subject: { id: 2, name: 'Writer' },
            role: 'MEMBER',
          },
          {
            subject_type: 'baserow_enterprise.Team',
            subject: { id: 3, name: 'Editors', subject_count: 2 },
            role: 'MEMBER',
          },
        ],
        scopeId: 1,
        scopeType: 'application',
        workspaceId: 1,
        teams: [{ id: 3, subject_count: 2 }],
      },
      global: {
        mocks: {
          $store: {
            getters: {
              'auth/getUserId': 1,
              'workspace/get': () => ({
                id: 1,
                _: {
                  roles: [
                    {
                      uid: 'MEMBER',
                      allowedSubjectTypes: null,
                    },
                  ],
                },
              }),
            },
          },
        },
        stubs: {
          RoleSelector: RoleSelectorStub,
        },
      },
    })

    expect(wrapper.html()).toMatchSnapshot()
  })

  test('shows admins of a higher level with a locked admin role and the reason', async () => {
    const RoleSelectorProbe = {
      props: { disabled: Boolean, value: Object, roles: Array },
      template:
        '<button class="role-selector" :disabled="disabled" :data-role="value.uid" :data-roles="roles.map((role) => role.uid).join()" />',
    }
    const HelpIconProbe = {
      props: { tooltip: String },
      template: '<i class="help-icon" :data-tooltip="tooltip" />',
    }
    const role = (uid) => ({
      uid,
      name: uid,
      isVisible: true,
      allowedScopeTypes: null,
      allowedSubjectTypes: null,
    })
    const wrapper = await mountSuspended(MemberRolesMembersList, {
      props: {
        roleAssignments: [
          {
            subject_type: 'auth.User',
            subject: { id: 2, first_name: 'Bob' },
            role: 'NO_ACCESS',
          },
          {
            subject_type: 'auth.User',
            subject: { id: 3, first_name: 'Carol' },
            role: 'ADMIN',
          },
          {
            subject_type: 'baserow_enterprise.Team',
            subject: { id: 4, name: 'Sales', subject_count: 1 },
            role: 'VIEWER',
          },
        ],
        scopeId: 1,
        scopeType: 'database_table',
        scopeTypeName: 'table',
        workspaceId: 1,
        teams: [{ id: 4, subject_count: 1 }],
        inheritedAdmins: { 'auth.User:2': 'workspace' },
      },
      global: {
        mocks: {
          $store: {
            getters: {
              'auth/getUserId': 1,
              'workspace/get': () => ({
                id: 1,
                _: {
                  roles: [role('ADMIN'), role('VIEWER'), role('NO_ACCESS')],
                },
              }),
            },
          },
        },
        stubs: {
          RoleSelector: RoleSelectorProbe,
          HelpIcon: HelpIconProbe,
        },
      },
    })

    const rows = wrapper.findAll('.list__item')
    const row = (name) => rows.find((item) => item.text().includes(name))

    // Bob is an admin of the workspace: his "no access" here has no effect, so
    // he is shown as an admin whose role can only be removed.
    expect(row('Bob').find('.role-selector').attributes('data-role')).toBe(
      'ADMIN'
    )
    expect(row('Bob').find('.role-selector').attributes('data-roles')).toBe(
      'ADMIN'
    )
    expect(row('Bob').find('.help-icon').attributes('data-tooltip')).toBe(
      'memberRolesMembersList.inheritedAdminHelpText'
    )

    // Carol is an admin of this table itself: her role can still be changed.
    expect(row('Carol').find('.role-selector').attributes('data-role')).toBe(
      'ADMIN'
    )
    expect(row('Carol').find('.role-selector').attributes('data-roles')).toBe(
      'ADMIN,VIEWER,NO_ACCESS'
    )
    expect(row('Carol').find('.help-icon').attributes('data-tooltip')).toBe(
      'memberRolesMembersList.scopeAdminHelpText'
    )

    expect(row('Sales').find('.role-selector').attributes('data-role')).toBe(
      'VIEWER'
    )
    expect(row('Sales').find('.help-icon').exists()).toBe(false)
  })
})
