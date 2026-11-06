import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import LinkInvitationRoute from '@baserow/modules/core/components/invitation/LinkInvitationRoute'
import ConfirmModal from '@baserow/modules/core/components/modals/ConfirmModal'
import InvitationLinkDeleteModal from '@baserow/modules/core/components/invitation/InvitationLinkDeleteModal'
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
    expect(url(rows(wrapper)[0])).toBe('/invite/second')
  })
})

describe('LinkInvitationRoute without roles', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    testApp.afterEach()
  })

  /**
   * A target that gives its own role, like a team, so its links have none.
   */
  function createTargetType({ grantsAdmin = false } = {}) {
    return {
      getTitle: () => null,
      getRoles: () => [],
      getInvitationLinkRole: () => ({ uid: 'EDITOR', name: 'Editor' }),
      getInvitationLinkRoleHelpText: () => 'The role comes from the team.',
      invitationLinkGrantsAdmin: vi.fn(() => grantsAdmin),
      getInvitationLinkAdminWarning: () => 'Anyone becomes an admin.',
      getInvitationLinkDeleteWarning: () => 'Delete it?',
      fetchInvitationLinks: vi.fn(async () => [
        { id: 1, name: 'Fair', slug: 'first' },
      ]),
      createInvitationLink: vi.fn(async () => ({
        id: 2,
        name: '',
        slug: 'second',
      })),
    }
  }

  async function mountRoute(targetType) {
    const wrapper = await testApp.mount(LinkInvitationRoute, {
      propsData: { workspace, target: { type: 'team' }, targetType },
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

  test('says what a link does in the empty state, without roles', async () => {
    const targetType = createTargetType()
    targetType.fetchInvitationLinks = vi.fn(async () => [])
    const wrapper = await mountRoute(targetType)

    expect(wrapper.find('.invitation-link-empty').text()).toContain(
      'inviteModal.linkEmptyDescriptionNoRole'
    )
  })

  test('shows the role of the target in a disabled role selector', async () => {
    const wrapper = await mountRoute(createTargetType())
    const selector = wrapper.findComponent(WorkspaceRoleSelector)

    expect(selector.props('modelValue')).toBe('EDITOR')
    expect(selector.props('roles')).toEqual([{ uid: 'EDITOR', name: 'Editor' }])
    expect(selector.attributes('class')).toContain('dropdown--disabled')
    expect(wrapper.findComponent({ name: 'HelpIcon' }).props('tooltip')).toBe(
      'The role comes from the team.'
    )
  })

  test('shows a disabled selector without role for a target giving none', async () => {
    const targetType = createTargetType()
    targetType.getInvitationLinkRole = () => null
    const wrapper = await mountRoute(targetType)
    const selector = wrapper.findComponent(WorkspaceRoleSelector)

    expect(selector.props('roles')).toEqual([])
    expect(selector.text()).toContain('inviteModal.linkNoRole')
  })

  test('creates a link without a role', async () => {
    const targetType = createTargetType()
    const wrapper = await mountRoute(targetType)
    const button = wrapper.find('.button-floating')

    expect(button.attributes('disabled')).toBeUndefined()
    await button.trigger('click')
    await flushPromises()

    expect(targetType.invitationLinkGrantsAdmin).toHaveBeenCalledWith(
      workspace,
      { type: 'team' },
      null
    )
    expect(targetType.createInvitationLink).toHaveBeenCalledWith(
      workspace,
      { type: 'team' },
      null
    )
    expect(wrapper.findAll('.invitation-links__item')).toHaveLength(2)
  })

  test('asks first when the target gives the admin role', async () => {
    const targetType = createTargetType({ grantsAdmin: true })
    const wrapper = await mountRoute(targetType)
    const confirmModal = wrapper.findComponent(ConfirmModal)
    const show = vi.spyOn(confirmModal.vm, 'show')

    await wrapper.find('.button-floating').trigger('click')
    await flushPromises()

    expect(show).toHaveBeenCalled()
    expect(targetType.createInvitationLink).not.toHaveBeenCalled()

    await confirmModal.find('button').trigger('click')
    await flushPromises()

    expect(targetType.createInvitationLink).toHaveBeenCalledTimes(1)
  })
})
