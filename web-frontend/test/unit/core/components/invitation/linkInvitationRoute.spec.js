import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import LinkInvitationRoute from '@baserow/modules/core/components/invitation/LinkInvitationRoute'
import ConfirmModal from '@baserow/modules/core/components/modals/ConfirmModal'
import InvitationLinkDeleteModal from '@baserow/modules/core/components/invitation/InvitationLinkDeleteModal'
import InvitationLinkPasswordModal from '@baserow/modules/core/components/invitation/InvitationLinkPasswordModal'
import WorkspaceRoleSelector from '@baserow/modules/core/components/workspace/WorkspaceRoleSelector'
import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'

vi.mock('@baserow/modules/core/utils/clipboard', () => ({
  copyToClipboard: vi.fn(),
}))

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
    return row.find('.invitation-links__url').text()
  }

  function nameInput(row) {
    return row.find('.invitation-links__name input')
  }

  test('shows the empty state when there are no links', async () => {
    mockLinks([])
    const wrapper = await mountRoute()

    expect(wrapper.find('.invitation-link-empty').exists()).toBe(true)
    expect(rows(wrapper)).toHaveLength(0)
  })

  test('lists the links with their name, role and URL', async () => {
    mockLinks([
      { id: 1, name: 'Marketing', slug: 'first', permissions: 'MEMBER' },
      { id: 2, name: '', slug: 'second', permissions: 'ADMIN' },
    ])
    const wrapper = await mountRoute()

    expect(rows(wrapper)).toHaveLength(2)
    expect(nameInput(rows(wrapper)[0]).element.value).toBe('Marketing')
    expect(url(rows(wrapper)[0])).toBe('/invite/first')
    const selectors = wrapper.findAllComponents(WorkspaceRoleSelector)
    expect(selectors.map((selector) => selector.props('modelValue'))).toEqual([
      'MEMBER',
      'ADMIN',
    ])
  })

  test.each(['.invitation-links__url', '.invitation-links__action'])(
    'copies the full URL and shows feedback when clicking %s',
    async (selector) => {
      mockLinks([{ id: 1, slug: 'first', permissions: 'MEMBER' }])
      const wrapper = await mountRoute()
      copyToClipboard.mockClear()

      await rows(wrapper)[0].find(selector).trigger('click')

      expect(copyToClipboard).toHaveBeenCalledExactlyOnceWith(
        'https://baserow.test/invite/first'
      )
      expect(rows(wrapper)[0].find('.copied--show').exists()).toBe(true)
    }
  )

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
    expect(url(rows(wrapper)[0])).toBe('/invite/new')
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

  test('renames a link when its name field loses focus', async () => {
    mockLinks([{ id: 1, name: '', slug: 'first', permissions: 'MEMBER' }])
    mockServer.mock
      .onPatch('/workspaces/invitation-links/1/')
      .reply(200, { id: 1, name: 'Freelancers', slug: 'first' })
    const wrapper = await mountRoute()
    const input = nameInput(rows(wrapper)[0])

    await input.setValue('  Freelancers ')
    await input.trigger('blur')
    await flushPromises()

    expect(mockServer.mock.history.patch).toHaveLength(1)
    expect(JSON.parse(mockServer.mock.history.patch[0].data)).toEqual({
      name: 'Freelancers',
    })

    await input.trigger('blur')
    await flushPromises()

    expect(mockServer.mock.history.patch).toHaveLength(1)
  })

  test('asks before a link grants the admin role', async () => {
    mockLinks([{ id: 1, slug: 'first', permissions: 'MEMBER' }])
    mockServer.mock
      .onPatch('/workspaces/invitation-links/1/')
      .reply(200, { id: 1, slug: 'first', permissions: 'ADMIN' })
    const wrapper = await mountRoute()
    const confirmModal = wrapper.findComponent(ConfirmModal)
    const show = vi.spyOn(confirmModal.vm, 'show')

    wrapper
      .findComponent(WorkspaceRoleSelector)
      .vm.$emit('update:modelValue', 'ADMIN')
    await flushPromises()

    expect(show).toHaveBeenCalled()
    expect(mockServer.mock.history.patch).toHaveLength(0)

    await confirmModal.find('button').trigger('click')
    await flushPromises()

    expect(mockServer.mock.history.patch).toHaveLength(1)
    expect(JSON.parse(mockServer.mock.history.patch[0].data)).toEqual({
      permissions: 'ADMIN',
    })
    await vi.waitFor(() => {
      expect(confirmModal.find('.modal__wrapper').exists()).toBe(false)
    })
  })

  test('cancels an admin role change without updating the link', async () => {
    mockLinks([{ id: 1, slug: 'first', permissions: 'MEMBER' }])
    const wrapper = await mountRoute()

    wrapper
      .findComponent(WorkspaceRoleSelector)
      .vm.$emit('update:modelValue', 'ADMIN')
    await flushPromises()

    const confirmModal = wrapper.findComponent(ConfirmModal)
    expect(confirmModal.text()).toContain(
      'invitationLinkAdminConfirmModal.message'
    )
    await confirmModal.find('.action__links a').trigger('click')
    await flushPromises()

    expect(mockServer.mock.history.patch).toHaveLength(0)
    await vi.waitFor(() => {
      expect(confirmModal.find('.modal__wrapper').exists()).toBe(false)
    })
    expect(
      wrapper.findComponent(WorkspaceRoleSelector).props('modelValue')
    ).toBe('MEMBER')
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
      .findAll('.invitation-links__action')[2]
      .trigger('click')
    await flushPromises()

    expect(show).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
    expect(mockServer.mock.history.delete).toHaveLength(0)
    expect(rows(wrapper)).toHaveLength(2)

    await deleteModal.vm.deleteInvitationLink()
    await flushPromises()

    expect(mockServer.mock.history.delete).toHaveLength(1)
    expect(rows(wrapper)).toHaveLength(1)
    expect(url(rows(wrapper)[0])).toBe('/invite/second')
  })

  test('protects a link with a password and removes it again', async () => {
    mockLinks([
      { id: 1, slug: 'first', permissions: 'MEMBER', has_password: false },
    ])
    mockServer.mock
      .onPatch('/workspaces/invitation-links/1/')
      .replyOnce(200, {
        id: 1,
        slug: 'first',
        permissions: 'MEMBER',
        has_password: true,
      })
      .onPatch('/workspaces/invitation-links/1/')
      .replyOnce(200, {
        id: 1,
        slug: 'first',
        permissions: 'MEMBER',
        has_password: false,
      })
    const wrapper = await mountRoute()
    const lock = () => rows(wrapper)[0].findAll('.invitation-links__action')[1]
    const passwordModal = wrapper.findComponent(InvitationLinkPasswordModal)
    const show = vi.spyOn(passwordModal.vm, 'show')

    expect(lock().classes()).not.toContain('invitation-links__action--active')
    await lock().trigger('click')
    expect(show).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))

    await passwordModal.vm.save('correct horse battery')
    await flushPromises()

    expect(JSON.parse(mockServer.mock.history.patch[0].data)).toEqual({
      password: 'correct horse battery',
    })
    expect(lock().classes()).toContain('invitation-links__action--active')

    await passwordModal.vm.save('')
    await flushPromises()

    expect(JSON.parse(mockServer.mock.history.patch[1].data)).toEqual({
      password: '',
    })
    expect(lock().classes()).not.toContain('invitation-links__action--active')
  })
})
