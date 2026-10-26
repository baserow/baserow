import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import WorkspaceInvitation from '@baserow/modules/core/components/workspace/WorkspaceInvitation'

const invitation = {
  id: 1,
  invited_by: 'Admin',
  workspace: 'Test workspace',
  email: 'user@example.com',
}

describe('WorkspaceInvitation', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
    testApp.authenticate({
      id: 1,
      username: 'user@example.com',
      email_verified: false,
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('offers a verification email when the email is not verified', async () => {
    testApp.dontFailOnErrorResponses()
    mockServer.mock.onPost('/workspaces/invitations/1/accept/').reply(400, {
      error: 'ERROR_GROUP_INVITATION_EMAIL_NOT_VERIFIED',
      detail: '',
    })
    mockServer.mock
      .onPost('/user/send-verify-email/', { email: 'user@example.com' })
      .reply(204)

    const wrapper = await testApp.mount(WorkspaceInvitation, {
      propsData: { invitation },
    })
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('workspaceInvitation.emailNotVerified')
    const button = wrapper.find('button')
    expect(button.text()).toBe('workspaceInvitation.sendVerificationEmail')

    await button.trigger('click')
    await flushPromises()
    expect(
      mockServer.mock.history.post.map((request) => request.url)
    ).toContain('/user/send-verify-email/')
  })

  test('sends the token and marks the email verified when accepting with it', async () => {
    mockServer.mock
      .onPost('/workspaces/invitations/1/accept/', { token: 'signed' })
      .reply(200, { id: 2, name: 'Test workspace' })

    await testApp.getStore().dispatch('auth/acceptWorkspaceInvitation', {
      invitationId: 1,
      token: 'signed',
    })

    expect(
      testApp.getStore().getters['auth/getUserObject'].email_verified
    ).toBe(true)
  })
})
