import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import InviteModal from '@baserow/modules/core/components/invitation/InviteModal'
import EmailInvitationRoute from '@baserow/modules/core/components/invitation/EmailInvitationRoute'
import LinkInvitationRoute from '@baserow/modules/core/components/invitation/LinkInvitationRoute'

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
  })

  afterEach(() => {
    vi.restoreAllMocks()
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

  async function mountAndFillForm() {
    const wrapper = await mountAndShow()
    await wrapper.find('input').setValue('test@example.com')
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
  })

  test('hides a route that is not enabled for the workspace', async () => {
    vi.spyOn(getLinkRoute(), 'isEnabled').mockReturnValue(false)

    const wrapper = await mountAndShow()

    expect(getNavLinks(wrapper).map((link) => link.text())).toEqual([
      'inviteModal.emailRoute',
    ])
    expect(getLinkRoute().isEnabled).toHaveBeenCalledWith(workspace)
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

  test('emits the invitation and closes after a successful invite', async () => {
    const invitation = { id: 1, workspace: 1, email: 'test@example.com' }
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .reply(200, invitation)
    const busEmit = vi.spyOn(testApp.getApp().$bus, '$emit')

    const wrapper = await mountAndFillForm()
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.emitted('invite-submitted')).toEqual([[invitation]])
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
    await wrapper.find('form').trigger('submit.prevent')
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
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    const body = JSON.parse(getInvitationRequests()[0].data)
    expect(body.captcha_token).toBeUndefined()
    expect(body.email).toBe('test@example.com')
  })

  test('does not render an empty container when the captcha is disabled', async () => {
    const wrapper = await mountAndFillForm()

    // Only the container of the submit button should be rendered, the captcha
    // widget must not leave an empty column behind.
    expect(wrapper.findAll('.col-12')).toHaveLength(1)
    expect(wrapper.html()).not.toContain('margin-top-2"><!--v-if-->')
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
    await wrapper.find('form').trigger('submit.prevent')
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
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.html()).toContain('error.captchaVerificationFailedTitle')
  })
})
