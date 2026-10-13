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

  async function mountAndShow() {
    const wrapper = await testApp.mount(InviteModal, {
      propsData: { workspace },
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

    expect(sendInvitation).toHaveBeenCalledWith(
      workspace,
      target,
      { email: 'test@example.com', permissions: 'VIEWER', captchaToken: '' },
      expect.stringContaining('/workspace-invitation')
    )
    expect(wrapper.emitted('invite-submitted')).toEqual([[[{ id: 7 }]]])
  })

  test('emits the invitation and closes after a successful invite', async () => {
    const invitation = { id: 1, workspace: 1, email: 'test@example.com' }
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .reply(200, invitation)
    const busEmit = vi.spyOn(testApp.getApp().$bus, '$emit')

    const wrapper = await mountAndFillForm()
    await submitInvites(wrapper)
    await flushPromises()

    expect(wrapper.emitted('invite-submitted')).toEqual([[[invitation]]])
    expect(busEmit).toHaveBeenCalledWith('invite-submitted', invitation)
    await waitForModalToClose()
    expect(wrapper.vm.$refs.modal.open).toBe(false)
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

  test('invites every picked address and closes with all of them', async () => {
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
    expect(wrapper.emitted('invite-submitted')).toEqual([[[first, second]]])
    await waitForModalToClose()
    expect(wrapper.vm.$refs.modal.open).toBe(false)
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
    expect(wrapper.emitted('invite-submitted')).toBeUndefined()
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
