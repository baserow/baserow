import flushPromises from 'flush-promises'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { TestApp } from '@baserow/test/helpers/testApp'
import InvitationLink from '@baserow/modules/core/pages/invitationLink.vue'

const { navigateToMock } = vi.hoisted(() => ({ navigateToMock: vi.fn() }))
mockNuxtImport('navigateTo', () => navigateToMock)

describe('Password protected invitation link page', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.mock.onGet('/settings/').reply(200, { allow_new_signups: true })
    navigateToMock.mockReset()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  // Each test uses its own slug, because the page caches the link by slug.
  async function mountLockedLink(slug) {
    testApp.mock
      .onGet(`/workspaces/invitation-links/slug/${slug}/`)
      .replyOnce(401, {
        error: 'ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED',
      })
      .onGet(`/workspaces/invitation-links/slug/${slug}/`)
      .reply(200, {
        slug,
        workspace: 'Acme',
        workspace_id: 1,
        invited_by: 'Ada',
        scope_name: null,
        role_upgrade: null,
      })
    const wrapper = await testApp.mount(InvitationLink, {
      route: `/invite/${slug}`,
    })
    await flushPromises()
    return wrapper
  }

  async function submitPassword(wrapper, password) {
    await wrapper.find('input[type="password"]').setValue(password)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
  }

  test('asks for the password before showing the link', async () => {
    const wrapper = await mountLockedLink('locked')

    expect(navigateToMock).not.toHaveBeenCalled()
    expect(wrapper.find('.auth__head-title').text()).toBe(
      'invitationLinkPassword.title'
    )
    expect(wrapper.text()).not.toContain('Acme')
  })

  test('keeps the form while sending a newcomer to the signup', async () => {
    const wrapper = await mountLockedLink('unlocked')
    testApp.mock
      .onPost('/workspaces/invitation-links/slug/unlocked/auth/')
      .reply(200, { access_token: 'link-token' })
    // The next page is still loading, so this one stays on screen.
    navigateToMock.mockReturnValue(new Promise(() => {}))

    await submitPassword(wrapper, 'correct horse battery')

    const linkRequests = testApp.mock.history.get.filter((request) =>
      request.url.endsWith('/slug/unlocked/')
    )
    expect(
      linkRequests.at(-1).headers['Baserow-Invitation-Link-Authorization']
    ).toBe('JWT link-token')
    expect(navigateToMock).toHaveBeenCalledWith(
      { name: 'signup', query: { invitationLinkSlug: 'unlocked' } },
      { replace: true }
    )
    // The join page must not flash before the signup replaces this page.
    expect(wrapper.find('.auth__head-title').text()).toBe(
      'invitationLinkPassword.title'
    )
    expect(wrapper.text()).not.toContain('invitationLinkJoin.join')
  })

  test('shows an error for a wrong password', async () => {
    const wrapper = await mountLockedLink('wrong')
    testApp.mock
      .onPost('/workspaces/invitation-links/slug/wrong/auth/')
      .reply(401, { error: 'ERROR_INVALID_CREDENTIALS' })

    await submitPassword(wrapper, 'not the password')

    expect(navigateToMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('invitationLinkPassword.incorrectTitle')
    expect(wrapper.find('button').attributes('disabled')).toBeUndefined()
  })
})
