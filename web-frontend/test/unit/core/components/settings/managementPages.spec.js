import { mount } from '@vue/test-utils'
import { describe, expect, test, beforeEach, afterEach } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import MembersTable from '@baserow/modules/core/components/settings/members/MembersTable'
import MembersInvitesTable from '@baserow/modules/core/components/settings/members/MembersInvitesTable'
import MemberRoleField from '@baserow/modules/core/components/settings/members/MemberRoleField'
import SidebarMenu from '@baserow/modules/core/components/sidebar/SidebarMenu'

describe('Management pages', () => {
  let app
  const roles = [
    { uid: 'ADMIN', name: 'Admin', icon: 'iconoir-crown' },
    { uid: 'MEMBER', name: 'Member', icon: 'iconoir-group' },
  ]
  const workspace = { id: 1, name: 'Design', users: [], _: { roles } }

  beforeEach(() => {
    app = new TestApp()
  })
  afterEach(async () => await app.afterEach())

  test('members retain their email and 2FA status alongside the new identity cell', async () => {
    app.mock.onGet('/workspaces/users/workspace/1/').reply(200, [
      {
        id: 10,
        user_id: 42,
        name: 'Alex Morgan',
        email: 'alex@example.com',
        permissions: 'ADMIN',
        two_factor_auth: { is_enabled: true },
      },
    ])
    app.authenticate({
      id: 42,
      first_name: 'Alex',
      username: 'alex@example.com',
    })
    const wrapper = await app.mount(MembersTable, {
      props: { workspace },
      global: {
        mocks: {
          $hasPermission: () => true,
          $t: (key, params) =>
            key === 'membersSettings.membersTable.title'
              ? `${params.userAmount} members`
              : key,
        },
      },
    })

    expect(wrapper.get('h1').text()).toBe('1 members')
    expect(wrapper.get('.management-name-field').text()).toContain(
      'Alex Morgan'
    )
    expect(wrapper.get('.management-name-field .badge').text()).toBe(
      'managementPages.you'
    )
    expect(wrapper.get('tbody').text()).toContain('alex@example.com')
    expect(wrapper.get('tbody').text()).toContain('twoFactorAuthField.enabled')
    expect(
      wrapper.get('.member-role-field__link').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.get('input').attributes('placeholder')).toBe(
      'membersSettings.membersTable.search'
    )
  })

  test('invites keep their email and role with a contextual search', async () => {
    app.mock
      .onGet('/workspaces/invitations/workspace/1/')
      .reply(200, [
        { id: 10, email: 'alex@example.com', permissions: 'MEMBER' },
      ])
    const wrapper = await app.mount(MembersInvitesTable, {
      props: { workspace },
      global: { mocks: { $hasPermission: () => true } },
    })
    expect(wrapper.get('tbody').text()).toContain('alex@example.com')
    expect(wrapper.get('.member-role-field__link').text()).toBe('Member')
    expect(wrapper.get('input').attributes('placeholder')).toBe(
      'membersSettings.invitesTable.search'
    )
  })

  test.each([
    [42, true, true],
    [7, false, true],
    [7, true, false],
  ])(
    'role control for user %s with permission %s is disabled=%s',
    async (userId, permitted, disabled) => {
      const wrapper = await app.mount(MemberRoleField, {
        props: {
          row: { id: 10, user_id: userId, permissions: 'MEMBER' },
          column: { additionalProps: { roles, userId: 42, workspaceId: 1 } },
        },
        global: { mocks: { $hasPermission: () => permitted } },
      })
      const button = wrapper.get('button')
      expect(button.element.disabled).toBe(disabled)
      await button.trigger('click')
      if (disabled) {
        expect(wrapper.emitted('edit-role-context')).toBeUndefined()
      } else {
        expect(wrapper.emitted('edit-role-context')[0][0].target).toBe(
          button.element
        )
      }
    }
  )

  test.each([
    ['settings-members', true],
    ['settings-invites', true],
    ['settings-teams', true],
    ['settings-agents', true],
    ['dashboard', false],
  ])('Members sidebar selection on %s is %s', async (name, active) => {
    const wrapper = mount(SidebarMenu, {
      props: { selectedWorkspace: workspace },
      global: {
        mocks: {
          $hasPermission: () => true,
          $t: (key) => key,
          $route: { name },
          $store: { getters: { 'notification/getUnreadCount': 0 } },
          $registry: { getAll: () => ({}) },
        },
        stubs: {
          NuxtLink: {
            template:
              '<slot href="/members" :navigate="() => {}" :should-prefetch="() => false" />',
          },
          SidebarSearch: true,
          NotificationPanel: true,
          TrashModal: true,
          WorkspaceMemberInviteModal: true,
        },
      },
    })
    expect(
      wrapper.get('[data-highlight="members"]').classes().includes('active')
    ).toBe(active)
    wrapper.unmount()
  })
})
