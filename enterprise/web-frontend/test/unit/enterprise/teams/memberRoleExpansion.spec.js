import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, test, vi } from 'vitest'
import MembersTable from '@baserow/modules/core/components/settings/members/MembersTable'
import { EnterpriseMembersPagePluginType } from '@baserow_enterprise/membersPagePluginTypes'

const roles = [
  { uid: 'VIEWER', name: 'Viewer', isVisible: true },
  { uid: 'BUILDER', name: 'Builder', isVisible: true },
]
const workspace = { id: 1, name: 'Design', _: { roles } }
const members = [
  {
    id: 1,
    user_id: 1,
    name: 'Alex',
    email: 'alex@example.com',
    permissions: 'VIEWER',
    role_uid: 'VIEWER',
    highest_role_uid: 'BUILDER',
    teams: [],
  },
  {
    id: 2,
    user_id: 2,
    name: 'Sam',
    email: 'sam@example.com',
    permissions: 'VIEWER',
    role_uid: 'VIEWER',
    highest_role_uid: 'VIEWER',
    teams: [],
  },
  {
    id: 3,
    user_id: 3,
    name: 'Lee',
    email: 'lee@example.com',
    permissions: 'VIEWER',
    role_uid: 'VIEWER',
    teams: [],
  },
]
let wrapper

afterEach(() => wrapper?.unmount())

async function mountMembers(enabled = true) {
  const get = vi.fn().mockResolvedValue({ data: members })
  const plugin = new EnterpriseMembersPagePluginType({
    app: {
      $i18n: { t: (key) => key },
      $hasFeature: () => enabled,
    },
  })
  wrapper = await mountSuspended(MembersTable, {
    props: { workspace },
    global: {
      mocks: {
        $client: { get },
        $hasPermission: () => true,
        $registry: { getAll: () => ({ enterprise: plugin }) },
        $store: {
          getters: { 'auth/getUserId': 99, 'workspace/get': () => workspace },
        },
      },
      stubs: {
        WorkspaceMemberInviteModal: true,
        EditMemberContext: true,
        EditRoleContext: { template: '<div />', methods: { toggle: vi.fn() } },
        TwoFactorAuthField: true,
      },
    },
  })
  return get
}

describe('Member role expansion', () => {
  test('expands the available highest role without fetching or inventing scope assignments', async () => {
    const get = await mountMembers()
    expect(wrapper.findAll('.data-table__expand')).toHaveLength(1)
    expect(wrapper.find('.member-role-summary').exists()).toBe(false)
    const toggle = wrapper.get('.data-table__expand')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('.member-role-summary .badge').text()).toBe('Builder')
    expect(wrapper.get('.member-role-summary td').attributes('colspan')).toBe(
      '2'
    )
    expect(wrapper.get('.member-role-summary').text()).toContain(
      'memberRoleSummary.description'
    )
    expect(wrapper.get('.data-table__row-group').text()).toContain('Viewer')
    expect(get).toHaveBeenCalledTimes(1)
    await toggle.trigger('click')
    expect(wrapper.find('.member-role-summary').exists()).toBe(false)
  })

  test('keeps role controls independent from row expansion', async () => {
    await mountMembers()
    await wrapper.get('.member-role-field__link').trigger('click')
    expect(wrapper.find('.member-role-summary').exists()).toBe(false)
  })

  test('does not offer enterprise expansion without RBAC', async () => {
    await mountMembers(false)
    expect(wrapper.find('.data-table__expand').exists()).toBe(false)
    expect(wrapper.find('.member-role-summary').exists()).toBe(false)
  })
})
