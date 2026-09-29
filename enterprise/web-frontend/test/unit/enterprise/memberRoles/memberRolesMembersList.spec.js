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
})
