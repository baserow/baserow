import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import InviteModal from '@baserow/modules/core/components/invitation/InviteModal'
import EmailInvitationRoute from '@baserow/modules/core/components/invitation/EmailInvitationRoute'
import LinkInvitationRoute from '@baserow/modules/core/components/invitation/LinkInvitationRoute'
import { InvitationTargetType } from '@baserow/modules/core/invitationTargetTypes'

const workspace = {
  id: 1,
  name: 'Test workspace',
  _: {
    roles: [
      {
        uid: 'ADMIN',
        name: 'Admin',
        description: '',
        isVisible: true,
        isDeactivated: false,
        isBillable: false,
        showIsBillable: false,
      },
    ],
  },
}

describe('InviteModal', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
    mockServer.mock.onGet('/workspaces/invitations/workspace/1/').reply(200, [])
  })

  afterEach(() => {
    vi.restoreAllMocks()
    if (testApp.getRegistry().exists('invitationTarget', 'fake')) {
      testApp.getRegistry().unregister('invitationTarget', 'fake')
    }
    testApp.afterEach()
  })

  function getLinkRoute() {
    return testApp.getRegistry().get('invitationRoute', 'link')
  }

  function getNavLinks(wrapper) {
    return wrapper.findAll('.modal-sidebar__nav-link')
  }

  async function mountAndShow({
    workspace: selectedWorkspace = workspace,
    hasPermission = () => true,
  } = {}) {
    const wrapper = await testApp.mount(InviteModal, {
      propsData: { workspace: selectedWorkspace },
      global: { mocks: { $hasPermission: hasPermission } },
    })
    await wrapper.vm.show()
    await flushPromises()
    return wrapper
  }

  async function pickEmails(wrapper, emails) {
    const input = wrapper.find('.invite-input__input')
    for (const email of emails) {
      await input.setValue(email)
      await input.trigger('keydown', { key: 'Enter' })
    }
  }

  function submitInvites(wrapper) {
    return wrapper.find('.invite-input__row button').trigger('click')
  }

  function chips(wrapper) {
    return wrapper.findAll('.invite-input__chip').map((chip) => chip.text())
  }

  function pendingEmails(wrapper) {
    return wrapper
      .findAll('.invite-list__name')
      .map((name) => name.text().trim())
  }

  async function mountAndFillForm(emails = ['test@example.com']) {
    const wrapper = await mountAndShow()
    await pickEmails(wrapper, emails)
    return wrapper
  }

  function getInvitationRequests() {
    return mockServer.mock.history.post.filter((request) =>
      request.url.startsWith('/workspaces/invitations/workspace/')
    )
  }

  // The modal only toggles its open state in a timeout after `hide`.
  function waitForModalToClose() {
    return new Promise((resolve) => setTimeout(resolve, 10))
  }

  test('lists the enabled invitation routes with the first one active', async () => {
    vi.spyOn(getLinkRoute(), 'isEnabled').mockReturnValue(true)

    const wrapper = await mountAndShow()

    const links = getNavLinks(wrapper)
    expect(links.map((link) => link.text())).toEqual([
      'inviteModal.emailRoute',
      'inviteModal.linkRoute',
    ])
    expect(links[0].classes()).toContain('active')
    expect(wrapper.findComponent(EmailInvitationRoute).exists()).toBe(true)
    expect(wrapper.findComponent(LinkInvitationRoute).exists()).toBe(false)
    // The workspace target has no header of its own.
    expect(wrapper.find('.invite-modal__header').exists()).toBe(false)
  })

  test('shows an empty state while no invitation is pending', async () => {
    const wrapper = await mountAndShow()

    expect(wrapper.find('.invite-list__empty').text()).toContain(
      'inviteModal.pendingEmptyTitle'
    )
    expect(wrapper.findAll('.invite-list__item')).toHaveLength(0)
  })

  test('lists the pending invitations and adds the ones it sends', async () => {
    mockServer.mock
      .onGet('/workspaces/invitations/workspace/1/')
      .reply(200, [{ id: 3, email: 'olga@x.com', permissions: 'ADMIN' }])
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .reply(200, { id: 4, email: 'new@x.com', permissions: 'ADMIN' })
    const wrapper = await mountAndFillForm(['new@x.com'])

    expect(wrapper.find('.invite-list__empty').exists()).toBe(false)
    const rows = () =>
      wrapper.findAll('.invite-list__item').map((row) => row.text())
    expect(rows()).toEqual([expect.stringMatching(/olga@x\.com\s*Admin/)])

    // The modal closes once everything was sent, so the list is read from the
    // route rather than from the rendered rows.
    const route = wrapper.findComponent(EmailInvitationRoute).vm
    await submitInvites(wrapper)
    await flushPromises()
    expect(route.invitations.map(({ email }) => email)).toEqual([
      'olga@x.com',
      'new@x.com',
    ])
  })

  test('shows pending invitation subtitles supplied by role metadata', async () => {
    mockServer.mock.onGet('/workspaces/invitations/workspace/1/').reply(200, [
      {
        id: 3,
        email: 'olga@x.com',
        permissions: 'CUSTOM_ROLE',
      },
    ])
    const wrapper = await mountAndShow({
      workspace: {
        ...workspace,
        _: {
          roles: [
            ...workspace._.roles,
            {
              uid: 'CUSTOM_ROLE',
              name: 'Custom role',
              isVisible: true,
              invitationSubtitle: 'customRole.invitationSubtitle',
            },
          ],
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('.invite-list__subtitle').text()).toBe(
      'customRole.invitationSubtitle'
    )
  })

  test('changes a pending workspace role and prevents overlapping updates', async () => {
    const invitation = {
      id: 3,
      workspace: 1,
      email: 'olga@x.com',
      permissions: 'ADMIN',
    }
    const selectedWorkspace = {
      ...workspace,
      _: {
        roles: [
          ...workspace._.roles,
          { uid: 'MEMBER', name: 'Member', isVisible: true },
        ],
      },
    }
    mockServer.mock
      .onGet('/workspaces/invitations/workspace/1/')
      .reply(200, [invitation])
    let respond
    mockServer.mock.onPatch('/workspaces/invitations/3/').reply(
      () =>
        new Promise((resolve) => {
          respond = resolve
        })
    )
    const busEmit = vi.spyOn(testApp.getApp().$bus, '$emit')
    const wrapper = await mountAndShow({ workspace: selectedWorkspace })
    try {
      const row = wrapper.find('.invite-list__item')
      await row.find('.invite-list__role > a').trigger('click')
      await row
        .findAll('.context__menu-item-link')
        .find((link) => link.text().trim() === 'Member')
        .trigger('click')
      await flushPromises()

      expect(mockServer.mock.history.patch).toHaveLength(1)
      expect(JSON.parse(mockServer.mock.history.patch[0].data)).toEqual({
        permissions: 'MEMBER',
      })
      expect(row.find('.invite-list__role > a').exists()).toBe(false)
      expect(row.find('.invite-list__role > span').text()).toBe('Admin')
      expect(busEmit).not.toHaveBeenCalledWith(
        'invite-updated',
        expect.anything()
      )

      const updated = { ...invitation, permissions: 'MEMBER' }
      respond([200, updated])
      await flushPromises()
      expect(row.find('.invite-list__role > a').text()).toBe('Member')
      expect(busEmit).toHaveBeenCalledWith('invite-updated', updated)
    } finally {
      respond?.([200, invitation])
    }
  })

  test('cancels a workspace invitation and allows its email to be invited again', async () => {
    const invitation = {
      id: 3,
      workspace: 1,
      email: 'olga@x.com',
      permissions: 'ADMIN',
    }
    mockServer.mock
      .onGet('/workspaces/invitations/workspace/1/')
      .reply(200, [invitation])
    mockServer.mock.onDelete('/workspaces/invitations/3/').reply(204)
    const busEmit = vi.spyOn(testApp.getApp().$bus, '$emit')
    const wrapper = await mountAndShow()

    const row = wrapper.find('.invite-list__item')
    await row.find('.invite-list__role > a').trigger('click')
    await row.find('.context__menu-item-link--delete').trigger('click')
    await flushPromises()

    expect(mockServer.mock.history.delete.map(({ url }) => url)).toEqual([
      '/workspaces/invitations/3/',
    ])
    expect(wrapper.find('.invite-list__empty').text()).toContain(
      'inviteModal.pendingEmptyTitle'
    )
    expect(busEmit).toHaveBeenCalledWith('invite-deleted', invitation)
    await pickEmails(wrapper, ['olga@x.com'])
    expect(wrapper.find('.invite-input__chip--error').exists()).toBe(false)
  })

  test.each(['patch', 'delete'])(
    'preserves the invitation and allows retry after a failed %s',
    async (method) => {
      testApp.dontFailOnErrorResponses()
      const invitation = {
        id: 3,
        workspace: 1,
        email: 'olga@x.com',
        permissions: 'ADMIN',
      }
      mockServer.mock
        .onGet('/workspaces/invitations/workspace/1/')
        .reply(200, [invitation])
      const selectedWorkspace = {
        ...workspace,
        _: {
          roles: [
            ...workspace._.roles,
            { uid: 'MEMBER', name: 'Member', isVisible: true },
          ],
        },
      }
      const adapter = method === 'patch' ? 'onPatch' : 'onDelete'
      mockServer.mock[adapter]('/workspaces/invitations/3/').replyOnce(500)
      mockServer.mock[adapter]('/workspaces/invitations/3/').reply(
        method === 'patch' ? 200 : 204,
        { ...invitation, permissions: 'MEMBER' }
      )
      const wrapper = await mountAndShow({ workspace: selectedWorkspace })
      const selectAction = async () => {
        const row = wrapper.find('.invite-list__item')
        await row.find('.invite-list__role > a').trigger('click')
        const link =
          method === 'delete'
            ? row.find('.context__menu-item-link--delete')
            : row
                .findAll('.context__menu-item-link')
                .find((link) => link.text().trim() === 'Member')
        await link.trigger('click')
        await flushPromises()
      }

      await selectAction()
      expect(wrapper.find('.invite-list__name').text()).toBe('olga@x.com')
      expect(wrapper.find('.invite-list__role > a').text()).toBe('Admin')
      await selectAction()
      expect(mockServer.mock.history[method]).toHaveLength(2)
      if (method === 'delete') {
        expect(wrapper.find('.invite-list__item').exists()).toBe(false)
      } else {
        expect(wrapper.find('.invite-list__role > a').text()).toBe('Member')
      }
    }
  )

  test('offers only cancellation when workspace role changes are not permitted', async () => {
    mockServer.mock
      .onGet('/workspaces/invitations/workspace/1/')
      .reply(200, [{ id: 3, email: 'olga@x.com', permissions: 'ADMIN' }])
    const wrapper = await mountAndShow({
      hasPermission: (operation) => operation === 'invitation.delete',
    })
    const row = wrapper.find('.invite-list__item')
    await row.find('.invite-list__role > a').trigger('click')
    expect(
      row.findAll('.context__menu-item-link').map((link) => link.text())
    ).toEqual(['action.remove'])
  })

  test('shows the role without controls when workspace invitation changes are not permitted', async () => {
    mockServer.mock
      .onGet('/workspaces/invitations/workspace/1/')
      .reply(200, [{ id: 3, email: 'olga@x.com', permissions: 'ADMIN' }])
    const wrapper = await mountAndShow({ hasPermission: () => false })
    const row = wrapper.find('.invite-list__item')
    expect(row.find('.invite-list__role > a').exists()).toBe(false)
    expect(row.find('.invite-list__role > span').text()).toBe('Admin')
    expect(mockServer.mock.history.patch).toHaveLength(0)
    expect(mockServer.mock.history.delete).toHaveLength(0)
  })

  test('hides a route that is not enabled for the workspace', async () => {
    vi.spyOn(getLinkRoute(), 'isEnabled').mockReturnValue(false)

    const wrapper = await mountAndShow()

    expect(getNavLinks(wrapper).map((link) => link.text())).toEqual([
      'inviteModal.emailRoute',
    ])
    expect(getLinkRoute().isEnabled).toHaveBeenCalledWith(workspace, {
      type: 'workspace',
    })
  })

  test('switches the content when another route is clicked', async () => {
    vi.spyOn(getLinkRoute(), 'isEnabled').mockReturnValue(true)
    const wrapper = await mountAndShow()

    await getNavLinks(wrapper)[1].trigger('click')

    expect(getNavLinks(wrapper)[1].classes()).toContain('active')
    expect(wrapper.findComponent(LinkInvitationRoute).exists()).toBe(true)
    expect(wrapper.findComponent(EmailInvitationRoute).exists()).toBe(false)
    expect(wrapper.html()).toContain('inviteModal.linkTitle')
    expect(wrapper.html()).toContain('inviteModal.linkEmptyTitle')
  })

  test('navigates in one modal, restores tabs with fresh data, and resets on reopen', async () => {
    class FakeInvitationTargetType extends InvitationTargetType {
      static getType() {
        return 'fake'
      }

      getNavigationLabel(workspace, target) {
        return target.level
      }

      getTitle(workspace, target) {
        return `Share ${target.name}`
      }
    }
    testApp
      .getRegistry()
      .register(
        'invitationTarget',
        new FakeInvitationTargetType({ app: testApp.getApp() })
      )
    let role = 'Admin'
    mockServer.mock.onGet('/navigation-demo/').reply(() => [200, { role }])
    mockServer.mock.onPatch('/navigation-demo/').reply(() => {
      role = 'Viewer'
      return [200, { role }]
    })
    const route = {
      props: ['target'],
      emits: ['navigate'],
      data: () => ({ role: '' }),
      async mounted() {
        const { data } = await testApp.getApp().$client.get('/navigation-demo/')
        this.role = data.role
      },
      methods: {
        async edit() {
          await testApp.getApp().$client.patch('/navigation-demo/')
        },
      },
      template: `<div class="navigation-demo">
        <span class="navigation-demo__role">{{ role }}</span>
        <button v-if="target.parent" class="navigation-demo__parent"
          @click="$emit('navigate', target.parent)">Parent</button>
        <button class="navigation-demo__edit" @click="edit">Edit</button>
      </div>`,
    }
    for (const type of ['email', 'link']) {
      const registered = testApp.getRegistry().get('invitationRoute', type)
      vi.spyOn(registered, 'isEnabled').mockReturnValue(true)
      vi.spyOn(registered, 'getComponent').mockReturnValue(route)
    }
    const database = { type: 'fake', name: 'Database', level: 'database' }
    const table = {
      type: 'fake',
      name: 'Table',
      level: 'table',
      parent: database,
    }
    const target = { type: 'fake', name: 'View', level: 'view', parent: table }
    const wrapper = await testApp.mount(InviteModal, {
      propsData: { workspace, target },
      global: {
        mocks: {
          $t: (key, params) =>
            key === 'inviteModal.backTo'
              ? `${key}: ${params.level}: ${params.title}`
              : key,
        },
      },
    })
    await wrapper.vm.show()
    await flushPromises()
    await getNavLinks(wrapper)[1].trigger('click')
    await wrapper.find('.navigation-demo__parent').trigger('click')
    await flushPromises()
    expect(wrapper.find('.invite-modal__title').text()).toBe('Share Table')
    expect(wrapper.find('.invite-modal__back').text()).toBe(
      'inviteModal.backTo: view: Share View'
    )
    expect(getNavLinks(wrapper)[0].classes()).toContain('active')
    await wrapper.find('.navigation-demo__parent').trigger('click')
    await flushPromises()
    expect(wrapper.find('.invite-modal__title').text()).toBe('Share Database')
    expect(wrapper.findAll('.modal__wrapper')).toHaveLength(1)
    await wrapper.find('.navigation-demo__edit').trigger('click')
    await flushPromises()
    await wrapper.find('.invite-modal__back').trigger('click')
    await flushPromises()
    expect(wrapper.find('.invite-modal__title').text()).toBe('Share Table')
    expect(wrapper.find('.navigation-demo__role').text()).toBe('Viewer')
    await wrapper.find('.invite-modal__back').trigger('click')
    await flushPromises()
    expect(wrapper.find('.invite-modal__title').text()).toBe('Share View')
    expect(getNavLinks(wrapper)[1].classes()).toContain('active')
    expect(wrapper.find('.navigation-demo__role').text()).toBe('Viewer')
    expect(wrapper.find('.invite-modal__back').exists()).toBe(false)

    await wrapper.find('.navigation-demo__parent').trigger('click')
    await flushPromises()
    await wrapper.find('.modal__close').trigger('click')
    await waitForModalToClose()
    expect(wrapper.find('.modal__wrapper').exists()).toBe(false)
    await wrapper.vm.show()
    await flushPromises()
    expect(wrapper.find('.invite-modal__title').text()).toBe('Share View')
    expect(wrapper.find('.invite-modal__back').exists()).toBe(false)
    expect(getNavLinks(wrapper)[0].classes()).toContain('active')
  })

  test('takes the roles and the request from the target type', async () => {
    const sendInvitation = vi.fn().mockResolvedValue({ id: 7 })
    class FakeInvitationTargetType extends InvitationTargetType {
      static getType() {
        return 'fake'
      }

      getRoles() {
        return [
          {
            uid: 'VIEWER',
            name: 'Fake viewer',
            description: '',
            isVisible: true,
            isDeactivated: false,
            isBillable: false,
            showIsBillable: false,
          },
        ]
      }

      getTitle(workspace, target) {
        return `Share ${target.name}`
      }

      getSubtitle() {
        return 'Somewhere / Deep'
      }

      sendInvitation(...args) {
        return sendInvitation(...args)
      }
    }
    testApp
      .getRegistry()
      .register(
        'invitationTarget',
        new FakeInvitationTargetType({ app: testApp.getApp() })
      )
    const target = { type: 'fake', name: 'the fake object' }
    // The email route only serves the workspace, so a route has to be enabled
    // explicitly for the fake target.
    vi.spyOn(
      testApp.getRegistry().get('invitationRoute', 'email'),
      'isEnabled'
    ).mockReturnValue(true)

    const wrapper = await testApp.mount(InviteModal, {
      propsData: { workspace, target },
    })
    await wrapper.vm.show()
    await flushPromises()

    expect(wrapper.find('.invite-modal__title').text()).toBe(
      'Share the fake object'
    )
    expect(wrapper.find('.invite-modal__subtitle').text()).toBe(
      'Somewhere / Deep'
    )
    expect(wrapper.html()).toContain('Fake viewer')

    await pickEmails(wrapper, ['test@example.com'])
    await submitInvites(wrapper)
    await flushPromises()

    expect(sendInvitation).toHaveBeenCalledWith(workspace, target, {
      email: 'test@example.com',
      permissions: 'VIEWER',
      captchaToken: '',
    })
    expect(wrapper.vm.$refs.modal.open).toBe(true)
  })

  test('lists the invitation and stays open after a successful invite', async () => {
    const invitation = { id: 1, workspace: 1, email: 'test@example.com' }
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .reply(200, invitation)
    const busEmit = vi.spyOn(testApp.getApp().$bus, '$emit')

    const wrapper = await mountAndFillForm()
    await submitInvites(wrapper)
    await flushPromises()

    expect(busEmit).toHaveBeenCalledWith('invite-submitted', invitation)
    expect(chips(wrapper)).toEqual([])
    expect(pendingEmails(wrapper)).toEqual(['test@example.com'])
    expect(wrapper.vm.$refs.modal.open).toBe(true)
  })

  test('sends the captcha token along with the invitation', async () => {
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .reply(200, { id: 1, workspace: 1, email: 'test@example.com' })

    const wrapper = await mountAndFillForm()
    wrapper
      .findComponent(EmailInvitationRoute)
      .vm.onCaptchaToken('a-captcha-token')
    await submitInvites(wrapper)
    await flushPromises()

    const requests = getInvitationRequests()
    expect(requests).toHaveLength(1)
    expect(JSON.parse(requests[0].data).captcha_token).toBe('a-captcha-token')
  })

  test('does not send a captcha token when there is none', async () => {
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .reply(200, { id: 1, workspace: 1, email: 'test@example.com' })

    const wrapper = await mountAndFillForm()
    await submitInvites(wrapper)
    await flushPromises()

    const body = JSON.parse(getInvitationRequests()[0].data)
    expect(body.captcha_token).toBeUndefined()
    expect(body.email).toBe('test@example.com')
  })

  test('does not render an empty container when the captcha is disabled', async () => {
    const wrapper = await mountAndFillForm()

    // The captcha widget must not leave an empty element behind.
    expect(wrapper.html()).not.toContain('margin-top-2"><!--v-if-->')
  })

  test('invites every picked address and lists all of them', async () => {
    const first = { id: 1, workspace: 1, email: 'first@example.com' }
    const second = { id: 2, workspace: 1, email: 'second@example.com' }
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .replyOnce(200, first)
      .onPost('/workspaces/invitations/workspace/1/')
      .replyOnce(200, second)

    const wrapper = await mountAndFillForm([
      'first@example.com',
      'second@example.com',
    ])
    expect(chips(wrapper)).toEqual(['first@example.com', 'second@example.com'])
    expect(wrapper.find('.invite-input__row button').text()).toContain(
      'inviteInput.inviteAs'
    )

    await submitInvites(wrapper)
    await flushPromises()

    const emails = getInvitationRequests().map(
      (request) => JSON.parse(request.data).email
    )
    expect(emails).toEqual(['first@example.com', 'second@example.com'])
    expect(pendingEmails(wrapper)).toEqual([
      'first@example.com',
      'second@example.com',
    ])
    expect(wrapper.vm.$refs.modal.open).toBe(true)
  })

  test('points out a pending invitation instead of sending it again', async () => {
    mockServer.mock
      .onGet('/workspaces/invitations/workspace/1/')
      .reply(200, [{ id: 3, workspace: 1, email: 'olga@example.com' }])

    const wrapper = await mountAndShow()
    const input = wrapper.find('.invite-input__input')
    await input.setValue('Olga@example.com')
    await input.trigger('keydown', { key: 'Enter' })

    // The address becomes a chip marked as an error, so nothing can be sent.
    expect(chips(wrapper)).toEqual(['olga@example.com'])
    expect(wrapper.find('.invite-input__chip--error').exists()).toBe(true)
    expect(
      wrapper.find('.invite-input__row button').attributes('disabled')
    ).toBeDefined()
  })

  test('keeps the addresses that were not invited when one fails', async () => {
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .replyOnce(200, { id: 1, workspace: 1, email: 'first@example.com' })
      .onPost('/workspaces/invitations/workspace/1/')
      .replyOnce(400, {
        error: 'ERROR_GROUP_USER_ALREADY_EXISTS',
        detail: 'The user is already a member.',
      })

    const wrapper = await mountAndFillForm([
      'first@example.com',
      'member@example.com',
      'third@example.com',
    ])
    await submitInvites(wrapper)
    await flushPromises()

    // The first address went out, the one that failed and the one after it
    // are still picked, and the modal stays open to explain.
    expect(chips(wrapper)).toEqual(['member@example.com', 'third@example.com'])
    expect(wrapper.html()).toContain(
      'membersSettings.membersInviteModal.errors.userAlreadyInWorkspace.title'
    )
    expect(pendingEmails(wrapper)).toEqual(['first@example.com'])
    expect(wrapper.vm.$refs.modal.open).toBe(true)
  })

  test('starts with a fresh captcha token when shown again', async () => {
    const wrapper = await mountAndShow()
    wrapper
      .findComponent(EmailInvitationRoute)
      .vm.onCaptchaToken('consumed-token')

    wrapper.vm.hide()
    await waitForModalToClose()
    await wrapper.vm.show()
    await flushPromises()

    // Captcha tokens are single use, so a token from a previous open could
    // already be consumed or expired.
    expect(wrapper.findComponent(EmailInvitationRoute).vm.captchaToken).toBe('')
  })

  test('shows an invitation specific message when rate limited', async () => {
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .reply(429, { detail: 'Request was throttled.' })

    const wrapper = await mountAndFillForm()
    await submitInvites(wrapper)
    await flushPromises()

    expect(wrapper.html()).toContain(
      'membersSettings.membersInviteModal.errors.tooManyInvitations.title'
    )
    expect(wrapper.html()).not.toContain('clientHandler.tooManyRequestsTitle')
  })

  test('shows a message when the captcha verification failed', async () => {
    mockServer.mock.onPost('/workspaces/invitations/workspace/1/').reply(400, {
      error: 'ERROR_CAPTCHA_VERIFICATION_FAILED',
      detail: 'Captcha verification failed.',
    })

    const wrapper = await mountAndFillForm()
    await submitInvites(wrapper)
    await flushPromises()

    expect(wrapper.html()).toContain('error.captchaVerificationFailedTitle')
  })
})
