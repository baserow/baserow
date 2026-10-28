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

  const mountInvitation = async ({ emailDeliveryEnabled = true } = {}) => {
    testApp.store.commit('settings/SET_SETTINGS', {
      email_delivery_enabled: emailDeliveryEnabled,
    })
    return await testApp.mount(WorkspaceInvitation, {
      propsData: { invitation },
    })
  }

  const buttonTexts = (wrapper) =>
    wrapper.findAll('button').map((button) => button.text())

  test('offers a verification email instead of accepting when the email is not verified', async () => {
    mockServer.mock
      .onPost('/user/send-verify-email/', { email: 'user@example.com' })
      .reply(204)

    const wrapper = await mountInvitation()

    expect(wrapper.text()).toContain('workspaceInvitation.emailNotVerified')
    expect(buttonTexts(wrapper)).toEqual([
      'workspaceInvitation.sendVerificationEmail',
      'workspaceInvitation.reject',
    ])

    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()
    expect(
      mockServer.mock.history.post.map((request) => request.url)
    ).toContain('/user/send-verify-email/')
  })

  test('offers to accept once the email is verified in another tab', async () => {
    const wrapper = await mountInvitation()

    testApp.store.dispatch('auth/forceUpdateUserData', {
      user: { email_verified: true },
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('workspaceInvitation.emailNotVerified')
    expect(buttonTexts(wrapper)).toEqual([
      'workspaceInvitation.accept',
      'workspaceInvitation.reject',
    ])
  })

  test('offers to accept when the instance cannot deliver emails', async () => {
    const wrapper = await mountInvitation({ emailDeliveryEnabled: false })

    expect(buttonTexts(wrapper)).toEqual([
      'workspaceInvitation.accept',
      'workspaceInvitation.reject',
    ])
  })

  test('rejects with an unverified email', async () => {
    mockServer.mock.onPost('/workspaces/invitations/1/reject/').reply(204)

    const wrapper = await mountInvitation()
    await wrapper.find('.alert__actions-button-text').trigger('click')
    await flushPromises()

    expect(
      mockServer.mock.history.post.map((request) => request.url)
    ).toContain('/workspaces/invitations/1/reject/')
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
