import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import WorkspaceMemberInviteModal from '@baserow/modules/core/components/workspace/WorkspaceMemberInviteModal'

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

describe('WorkspaceMemberInviteModal', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
  })

  afterEach(() => {
    testApp.afterEach()
  })

  async function mountAndFillForm() {
    const wrapper = await testApp.mount(WorkspaceMemberInviteModal, {
      propsData: { workspace },
    })
    await wrapper.vm.show()
    await flushPromises()
    await wrapper.find('input').setValue('test@example.com')
    return wrapper
  }

  function getInvitationRequests() {
    return mockServer.mock.history.post.filter((request) =>
      request.url.startsWith('/workspaces/invitations/workspace/')
    )
  }

  test('sends the captcha token along with the invitation', async () => {
    mockServer.mock
      .onPost('/workspaces/invitations/workspace/1/')
      .reply(200, { id: 1, workspace: 1, email: 'test@example.com' })

    const wrapper = await mountAndFillForm()
    wrapper.vm.captchaToken = 'a-captcha-token'
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

  test('clears the captcha token when shown again', async () => {
    const wrapper = await testApp.mount(WorkspaceMemberInviteModal, {
      propsData: { workspace },
    })
    wrapper.vm.captchaToken = 'consumed-token'

    await wrapper.vm.show()

    expect(wrapper.vm.captchaToken).toBe('')
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
