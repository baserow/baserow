import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import LinkInvitationRoute from '@baserow/modules/core/components/invitation/LinkInvitationRoute'
import InvitationLinkAdminConfirmModal from '@baserow/modules/core/components/invitation/InvitationLinkAdminConfirmModal'
import InvitationLinkDeleteModal from '@baserow/modules/core/components/invitation/InvitationLinkDeleteModal'
import WorkspaceRoleSelector from '@baserow/modules/core/components/workspace/WorkspaceRoleSelector'

const roles = [
  {
    uid: 'ADMIN',
    name: 'Admin',
    description: '',
    isVisible: true,
    isDeactivated: false,
    isDefaultForInvitations: false,
  },
  {
    uid: 'MEMBER',
    name: 'Member',
    description: '',
    isVisible: true,
    isDeactivated: false,
    isDefaultForInvitations: true,
  },
]

const workspace = { id: 1, name: 'Test workspace', _: { roles } }

describe('LinkInvitationRoute', () => {
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

  function mockLinks(links) {
    mockServer.mock
      .onGet('/workspaces/invitation-links/workspace/1/')
      .reply(200, links)
  }

  async function mountRoute() {
    const target = { type: 'workspace' }
    const wrapper = await testApp.mount(LinkInvitationRoute, {
      propsData: {
        workspace,
        target,
        targetType: testApp.getRegistry().get('invitationTarget', 'workspace'),
      },
      global: {
        mocks: {
          $config: { public: { publicWebFrontendUrl: 'https://baserow.test' } },
          $router: {
            resolve: ({ params }) => ({ href: `/invite/${params.slug}` }),
          },
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  function rows(wrapper) {
    return wrapper.findAll('.invitation-links__item')
  }

  function url(row) {
    return row.find('.invitation-links__url input').element.value
  }

  test('shows the empty state when there are no links', async () => {
    mockLinks([])
    const wrapper = await mountRoute()

    expect(wrapper.find('.invitation-link-empty').exists()).toBe(true)
    expect(rows(wrapper)).toHaveLength(0)
  })

  test('lists the links with their role and URL', async () => {
    mockLinks([
      { id: 1, slug: 'first', permissions: 'MEMBER' },
      { id: 2, slug: 'second', permissions: 'ADMIN' },
    ])
    const wrapper = await mountRoute()

    expect(rows(wrapper)).toHaveLength(2)
    expect(url(rows(wrapper)[0])).toBe('https://baserow.test/invite/first')
    const selectors = wrapper.findAllComponents(WorkspaceRoleSelector)
    expect(selectors.map((selector) => selector.props('modelValue'))).toEqual([
      'MEMBER',
      'ADMIN',
    ])
  })

  test('creates a link with the default invitation role', async () => {
    mockLinks([])
    mockServer.mock
      .onPost('/workspaces/invitation-links/workspace/1/')
      .reply(200, { id: 3, slug: 'new', permissions: 'MEMBER' })
    const wrapper = await mountRoute()

    await wrapper.find('.button-floating').trigger('click')
    await flushPromises()

    expect(mockServer.mock.history.post).toHaveLength(1)
    expect(JSON.parse(mockServer.mock.history.post[0].data)).toEqual({
      permissions: 'MEMBER',
    })
    expect(rows(wrapper)).toHaveLength(1)
    expect(url(rows(wrapper)[0])).toBe('https://baserow.test/invite/new')
  })

  test('changes the role of a link right away', async () => {
    mockLinks([{ id: 1, slug: 'first', permissions: 'ADMIN' }])
    mockServer.mock
      .onPatch('/workspaces/invitation-links/1/')
      .reply(200, { id: 1, slug: 'first', permissions: 'MEMBER' })
    const wrapper = await mountRoute()

    wrapper
      .findComponent(WorkspaceRoleSelector)
      .vm.$emit('update:modelValue', 'MEMBER')
    await flushPromises()

    expect(mockServer.mock.history.patch).toHaveLength(1)
    expect(JSON.parse(mockServer.mock.history.patch[0].data)).toEqual({
      permissions: 'MEMBER',
    })
    expect(
      wrapper.findComponent(WorkspaceRoleSelector).props('modelValue')
    ).toBe('MEMBER')
  })

  test('asks before a link grants the admin role', async () => {
    mockLinks([{ id: 1, slug: 'first', permissions: 'MEMBER' }])
    mockServer.mock
      .onPatch('/workspaces/invitation-links/1/')
      .reply(200, { id: 1, slug: 'first', permissions: 'ADMIN' })
    const wrapper = await mountRoute()
    const confirmModal = wrapper.findComponent(InvitationLinkAdminConfirmModal)
    const show = vi.spyOn(confirmModal.vm, 'show')

    wrapper
      .findComponent(WorkspaceRoleSelector)
      .vm.$emit('update:modelValue', 'ADMIN')
    await flushPromises()

    expect(show).toHaveBeenCalled()
    expect(mockServer.mock.history.patch).toHaveLength(0)

    confirmModal.vm.$emit('confirm')
    await flushPromises()

    expect(mockServer.mock.history.patch).toHaveLength(1)
    expect(JSON.parse(mockServer.mock.history.patch[0].data)).toEqual({
      permissions: 'ADMIN',
    })
  })

  test('deletes a link only after confirming', async () => {
    mockLinks([
      { id: 1, slug: 'first', permissions: 'MEMBER' },
      { id: 2, slug: 'second', permissions: 'MEMBER' },
    ])
    mockServer.mock.onDelete('/workspaces/invitation-links/1/').reply(204)
    const wrapper = await mountRoute()
    const deleteModal = wrapper.findComponent(InvitationLinkDeleteModal)
    const show = vi.spyOn(deleteModal.vm, 'show')

    await rows(wrapper)[0]
      .findAll('.invitation-links__action')[1]
      .trigger('click')
    await flushPromises()

    expect(show).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
    expect(mockServer.mock.history.delete).toHaveLength(0)
    expect(rows(wrapper)).toHaveLength(2)

    await deleteModal.vm.deleteInvitationLink()
    await flushPromises()

    expect(mockServer.mock.history.delete).toHaveLength(1)
    expect(rows(wrapper)).toHaveLength(1)
    expect(url(rows(wrapper)[0])).toBe('https://baserow.test/invite/second')
  })
})
