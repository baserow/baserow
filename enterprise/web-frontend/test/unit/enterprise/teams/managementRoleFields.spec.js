import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, test, vi } from 'vitest'
import MembersRoleField from '@baserow_enterprise/components/MembersRoleField'
import TeamRoleField from '@baserow_enterprise/components/crudTable/fields/TeamRoleField'
import InvitesRoleField from '@baserow_enterprise/components/InvitesRoleField'
import { NoRoleLowPriorityRoleType } from '@baserow_enterprise/roleTypes'
import RolesService from '@baserow/modules/core/services/roles'

const roles = [
  { uid: 'VIEWER', name: 'Viewer', icon: 'iconoir-star', isVisible: true },
]
const workspace = { id: 1, _: { roles } }
const row = {
  id: 10,
  user_id: 7,
  role_uid: 'VIEWER',
  default_role: 'VIEWER',
  permissions: 'VIEWER',
}

describe('Enterprise management role controls', () => {
  test.each([
    [MembersRoleField, false, 42, true],
    [MembersRoleField, true, 7, true],
    [MembersRoleField, true, 42, false],
    [TeamRoleField, false, 42, true],
    [TeamRoleField, true, 42, false],
    [InvitesRoleField, true, 42, false],
  ])(
    '%s preserves permission=%s and current user=%s',
    async (component, permitted, currentUserId, disabled) => {
      const toggle = vi.fn()
      const wrapper = await mountSuspended(component, {
        props: {
          row,
          column: { key: 'role_uid', additionalProps: { workspaceId: 1 } },
        },
        global: {
          mocks: {
            $hasPermission: () => permitted,
            $store: {
              getters: {
                'workspace/get': () => workspace,
                'auth/getUserId': currentUserId,
              },
            },
          },
          stubs: {
            EditRoleContext: { template: '<div />', methods: { toggle } },
          },
        },
      })
      const button = wrapper.get('button')
      expect(button.text()).toBe('Viewer')
      expect(button.find('.iconoir-star').exists()).toBe(true)
      expect(button.element.disabled).toBe(disabled)
      await button.trigger('click')
      if (disabled) expect(toggle).not.toHaveBeenCalled()
      else expect(toggle).toHaveBeenCalledWith(button.element)
      wrapper.unmount()
    }
  )
})

test('renders the registered No role icon in the member role control', async () => {
  const roleType = new NoRoleLowPriorityRoleType({
    app: { $i18n: { t: (key) => key }, $hasFeature: () => true },
  })
  const registry = { getAll: () => ({ noRoleLowPriority: roleType }) }
  const { data } = RolesService(null, null, registry).get({ id: 1 })
  const roles = data.map((role) => ({ ...role, name: 'No role' }))
  const wrapper = await mountSuspended(MembersRoleField, {
    props: {
      row: { ...row, role_uid: 'NO_ROLE_LOW_PRIORITY' },
      column: { key: 'role_uid', additionalProps: { workspaceId: 1 } },
    },
    global: {
      mocks: {
        $hasPermission: () => true,
        $store: {
          getters: {
            'workspace/get': () => ({ id: 1, _: { roles } }),
            'auth/getUserId': 42,
          },
        },
      },
      stubs: { EditRoleContext: true },
    },
  })
  expect(wrapper.get('button').text()).toBe('No role')
  expect(wrapper.find('button .iconoir-minus').exists()).toBe(true)
  wrapper.unmount()
})
