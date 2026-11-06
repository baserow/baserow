import flushPromises from 'flush-promises'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { TestApp } from '@baserow/test/helpers/testApp'
import { createWorkspace } from '@baserow/test/fixtures/workspaces'
import InvitationLink from '@baserow/modules/core/pages/invitationLink.vue'

const { navigateToMock } = vi.hoisted(() => ({ navigateToMock: vi.fn() }))
mockNuxtImport('navigateTo', () => navigateToMock)

describe('Invitation link page', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.authenticate({ id: 1, username: 'dev@baserow.io' })
    testApp.mock.onGet('/settings/').reply(200, {})
    createWorkspace(testApp.mock, { workspaceId: 1 })
    navigateToMock.mockReset()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  // Each test uses its own slug, because the page caches the link by slug.
  async function mountWithLink(slug, link) {
    testApp.mock
      .onGet(`/workspaces/invitation-links/slug/${slug}/`)
      .reply(200, {
        slug,
        workspace: 'Acme',
        workspace_id: 1,
        invited_by: null,
        scope_name: 'Sales',
        role_upgrade: null,
        adds_member: false,
        ...link,
      })
    const wrapper = await testApp.mount(InvitationLink, {
      route: `/invite/${slug}`,
    })
    await flushPromises()
    return wrapper
  }

  test('keeps a member whom the link adds to its object on the page', async () => {
    const wrapper = await mountWithLink('addsmember', { adds_member: true })

    expect(navigateToMock).not.toHaveBeenCalled()
    expect(wrapper.find('.auth__head-title').text()).toBe(
      'invitationLinkJoin.addMemberTitle'
    )
    expect(wrapper.text()).toContain('invitationLinkJoin.addMember')
    expect(wrapper.find('button').text()).toBe(
      'invitationLinkJoin.addMemberButton'
    )
  })

  test('sends a member to the workspace when the link changes nothing', async () => {
    await mountWithLink('changesnothing', { adds_member: false })

    expect(navigateToMock).toHaveBeenCalledWith(
      { name: 'workspace', params: { workspaceId: 1 } },
      { replace: true }
    )
  })
})
