import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, test, beforeEach, afterEach, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import MembersTable from '@baserow/modules/core/components/settings/members/MembersTable'
import MemberRoleField from '@baserow/modules/core/components/settings/members/MemberRoleField'
import SidebarMenu from '@baserow/modules/core/components/sidebar/SidebarMenu'

describe('Management pages', () => {
  let app
  const roles = [
    { uid: 'ADMIN', name: 'Admin', icon: 'iconoir-crown' },
    { uid: 'MEMBER', name: 'Member', icon: 'baserow-icon-team' },
  ]
  const workspace = { id: 1, name: 'Design', users: [], _: { roles } }

  beforeEach(() => {
    app = new TestApp()
  })
  afterEach(async () => await app.afterEach())

  test.each([
    [true, 3],
    [false, 1],
  ])(
    'members retain their identity and permitted total (agents visible: %s)',
    async (canListAgents, memberCount) => {
      app.mock.onGet('/workspaces/users/workspace/1/').reply(200, [
        {
          id: 10,
          user_id: 42,
          name: 'Alex Taylor Morgan',
          email: 'alex@example.com',
          permissions: 'ADMIN',
          two_factor_auth: { is_enabled: true },
        },
      ])
      app.mock.onGet('/workspaces/invitations/workspace/1/').reply(200, [])
      app.authenticate({
        id: 42,
        first_name: 'Alex',
        username: 'alex@example.com',
      })
      const wrapper = await app.mount(MembersTable, {
        props: {
          workspace: { ...workspace, users: [{ id: 42 }], agents_count: 2 },
        },
        global: {
          mocks: {
            $hasPermission: (operation) =>
              operation !== 'workspace.list_agents' || canListAgents,
            $t: (key, params) =>
              key === 'membersSettings.membersTable.title'
                ? `${params.userAmount} members`
                : key,
          },
        },
      })

      expect(wrapper.get('h1').text()).toBe(`${memberCount} members`)
      expect(wrapper.get('.management-name-field').text()).toContain(
        'Alex Taylor Morgan'
      )
      expect(
        wrapper.get('.management-name-field .avatar__initials').text()
      ).toBe('AM')
      expect(wrapper.get('.management-name-field .badge').text()).toBe(
        'managementPages.you'
      )
      expect(wrapper.get('tbody').text()).toContain('alex@example.com')
      expect(wrapper.get('tbody').text()).toContain(
        'twoFactorAuthField.enabled'
      )
      expect(
        wrapper.get('.member-role-field__link').attributes('disabled')
      ).toBeDefined()
      expect(wrapper.get('input').attributes('placeholder')).toBe(
        'membersSettings.membersTable.search'
      )
    }
  )

  const mountMembersTable = (hasPermission = () => true) => {
    app.mock.onGet('/workspaces/users/workspace/1/').reply(200, [])
    return app.mount(MembersTable, {
      props: { workspace },
      global: {
        mocks: {
          $hasPermission: hasPermission,
          $t: (key, params) =>
            key === 'membersSettings.membersTable.pendingInvitations'
              ? `Pending invitations (${params.count})`
              : key,
        },
      },
    })
  }
  const pendingInvitationsButton = (wrapper) =>
    wrapper
      .findAll('.data-table__actions .button')
      .find((button) => button.text().startsWith('Pending invitations'))

  test('pending invitations are counted and open the invite modal', async () => {
    app.mock.onGet('/workspaces/invitations/workspace/1/').reply(200, [
      { id: 10, workspace: 1, email: 'alex@example.com' },
      { id: 11, workspace: 1, email: 'sam@example.com' },
    ])
    const wrapper = await mountMembersTable()
    await flushPromises()

    const button = pendingInvitationsButton(wrapper)
    expect(button.text()).toBe('Pending invitations (2)')
    const show = vi.spyOn(wrapper.vm.$refs.inviteModal, 'show')
    await button.trigger('click')
    expect(show).toHaveBeenCalled()
  })

  test('pending invitations are not offered when there are none', async () => {
    app.mock.onGet('/workspaces/invitations/workspace/1/').reply(200, [])
    const wrapper = await mountMembersTable()
    await flushPromises()

    expect(pendingInvitationsButton(wrapper)).toBeUndefined()
  })

  test('pending invitations are not fetched without the permission to list them', async () => {
    const wrapper = await mountMembersTable(
      (operation) => operation !== 'workspace.list_invitations'
    )
    await flushPromises()

    expect(pendingInvitationsButton(wrapper)).toBeUndefined()
    expect(
      app.mock.history.get.filter(({ url }) =>
        url.startsWith('/workspaces/invitations/')
      )
    ).toHaveLength(0)
  })

  test('pending invitations are recounted when one is sent from the modal', async () => {
    app.mock
      .onGet('/workspaces/invitations/workspace/1/')
      .replyOnce(200, [])
      .onGet('/workspaces/invitations/workspace/1/')
      .replyOnce(200, [{ id: 10, workspace: 1, email: 'alex@example.com' }])
    const wrapper = await mountMembersTable()
    await flushPromises()
    expect(pendingInvitationsButton(wrapper)).toBeUndefined()

    wrapper.vm.$bus.$emit('invite-submitted', { id: 10, workspace: 1 })
    await flushPromises()

    expect(pendingInvitationsButton(wrapper).text()).toBe(
      'Pending invitations (1)'
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
