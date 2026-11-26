import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import InvitationLinksTable from '@baserow/modules/core/components/settings/invitationLinks/InvitationLinksTable'
import ConfirmModal from '@baserow/modules/core/components/modals/ConfirmModal'
import CrudTableSearch from '@baserow/modules/core/components/crudTable/CrudTableSearch'
import InvitationLinkDeleteModal from '@baserow/modules/core/components/invitation/InvitationLinkDeleteModal'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'
import { InvitationTargetType } from '@baserow/modules/core/invitationTargetTypes'
import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'

vi.mock('@baserow/modules/core/utils/clipboard', () => ({
  copyToClipboard: vi.fn(),
}))

const roles = [
  { uid: 'ADMIN', name: 'Admin', isVisible: true, isDeactivated: false },
  { uid: 'MEMBER', name: 'Member', isVisible: true, isDeactivated: false },
]

const workspace = { id: 1, name: 'Acme', _: { roles } }

const URL = '/workspaces/invitation-links/workspace/1/manageable/'

/**
 * Stands in for the targets that enterprise registers, so that a link to an
 * object gets the same treatment as one to the workspace.
 */
class TableInvitationTargetType extends InvitationTargetType {
  static getType() {
    return 'test_table'
  }

  getRoles() {
    return []
  }

  getInvitationLinkRole() {
    return { uid: 'EDITOR', name: 'Editor' }
  }

  getTargetFromInvitationLink(workspace, invitationLink) {
    return invitationLink.scope_type === 'test_object'
      ? { type: 'test_table', scope: invitationLink.scope }
      : null
  }

  getInvitationLinkTargetName(workspace, { scope }) {
    return `Table: ${scope.name}`
  }

  deleteInvitationLink = vi.fn().mockResolvedValue()
}

const workspaceLink = {
  id: 1,
  name: 'Everyone',
  slug: 'everyone',
  permissions: 'MEMBER',
  has_password: true,
  scope_type: null,
  scope: null,
}

const tableLink = {
  id: 2,
  name: '',
  slug: 'customers',
  permissions: 'EDITOR',
  has_password: false,
  scope_type: 'test_object',
  scope: { id: 5, name: 'Customers' },
}

describe('InvitationLinksTable', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
    testApp
      .getRegistry()
      .register(
        'invitationTarget',
        new TableInvitationTargetType({ app: testApp.getApp() })
      )
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  async function mountTable(links) {
    mockServer.mock.onGet(URL).reply(200, links)
    const wrapper = await testApp.mount(InvitationLinksTable, {
      props: { workspace },
    })
    await flushPromises()
    return wrapper
  }

  function rows(wrapper) {
    return wrapper.findAll('tbody .data-table__table-row')
  }

  test('explains where links are created when there are none', async () => {
    const wrapper = await mountTable([])

    expect(wrapper.find('.placeholder').text()).toContain(
      'invitationLinksSettings.emptyTitle'
    )
    expect(wrapper.find('.data-table__actions .button').exists()).toBe(false)
  })

  test('lists the links to the workspace and to its objects', async () => {
    const wrapper = await mountTable([workspaceLink, tableLink])

    const [first, second] = rows(wrapper)
    expect(first.text()).toContain('Everyone')
    expect(first.text()).toContain('invitationLinksSettings.workspaceTarget')
    expect(first.text()).toContain('Member')
    expect(first.find('.iconoir-lock').exists()).toBe(true)
    expect(second.text()).toContain('invitationLinksSettings.unnamed')
    expect(second.text()).toContain('Table: Customers')
    // The table gives its own role, which can't be changed here.
    expect(second.text()).toContain('Editor')
    expect(second.find('.member-role-field__link').attributes()).toHaveProperty(
      'disabled'
    )
    expect(second.find('.iconoir-lock').exists()).toBe(false)
  })

  test('leaves out links of a target that is not available', async () => {
    const wrapper = await mountTable([
      workspaceLink,
      { ...tableLink, scope_type: 'unknown' },
    ])

    expect(rows(wrapper)).toHaveLength(1)
  })

  test('searches the links by name and target', async () => {
    const wrapper = await mountTable([workspaceLink, tableLink])

    wrapper
      .findComponent(CrudTableSearch)
      .vm.$emit('search-changed', 'customers')
    await flushPromises()

    expect(rows(wrapper)).toHaveLength(1)
    expect(rows(wrapper)[0].text()).toContain('Table: Customers')
    // The links are only fetched once, so searching doesn't reload them.
    expect(mockServer.mock.history.get).toHaveLength(1)
  })

  test('sorts from A to Z first, like the other management tables', async () => {
    const wrapper = await mountTable([
      { ...workspaceLink, id: 1, name: 'Beta' },
      { ...workspaceLink, id: 2, name: 'Alpha' },
      { ...workspaceLink, id: 3, name: 'Gamma' },
    ])
    const names = () =>
      rows(wrapper).map((row) =>
        row.find('.management-name-field__name').text()
      )
    const sortByName = () =>
      wrapper.find('.data-table__table-cell-head-link').trigger('click')

    await sortByName()
    await flushPromises()
    expect(names()).toEqual(['Alpha', 'Beta', 'Gamma'])

    await sortByName()
    await flushPromises()
    expect(names()).toEqual(['Gamma', 'Beta', 'Alpha'])
  })

  test('copies the full URL of a link', async () => {
    const wrapper = await mountTable([workspaceLink])
    copyToClipboard.mockClear()

    await wrapper
      .find('.invitation-link-actions-field__action')
      .trigger('click')

    expect(copyToClipboard).toHaveBeenCalledTimes(1)
    expect(copyToClipboard.mock.calls[0][0]).toMatch(/\/invite\/everyone$/)
  })

  test('changes the role of a link, after a confirmation for admin', async () => {
    mockServer.mock
      .onPatch('/workspaces/invitation-links/1/')
      .reply(200, { ...workspaceLink, permissions: 'ADMIN' })
    const wrapper = await mountTable([workspaceLink])
    const confirmModal = wrapper.findComponent(ConfirmModal)
    const show = vi.spyOn(confirmModal.vm, 'show')

    wrapper
      .findComponent(EditRoleContext)
      .vm.$emit('update-role', { uid: 'ADMIN', subject: workspaceLink })
    await flushPromises()

    expect(show).toHaveBeenCalled()
    expect(mockServer.mock.history.patch).toHaveLength(0)

    confirmModal.vm.$emit('confirm')
    await flushPromises()

    expect(JSON.parse(mockServer.mock.history.patch[0].data)).toEqual({
      permissions: 'ADMIN',
    })
    expect(rows(wrapper)[0].text()).toContain('Admin')
  })

  test('deletes a link through its target after the confirmation', async () => {
    const wrapper = await mountTable([workspaceLink, tableLink])
    const tableTargetType = testApp
      .getRegistry()
      .get('invitationTarget', 'test_table')

    await rows(wrapper)[1]
      .findAll('.invitation-link-actions-field__action')[1]
      .trigger('click')
    await flushPromises()
    const deleteModal = wrapper.findComponent(InvitationLinkDeleteModal)
    expect(deleteModal.props('target')).toEqual({
      type: 'test_table',
      scope: tableLink.scope,
    })
    await deleteModal.vm.deleteInvitationLink()
    await flushPromises()

    expect(tableTargetType.deleteInvitationLink).toHaveBeenCalledWith(
      workspace,
      { type: 'test_table', scope: tableLink.scope },
      expect.objectContaining({ id: 2 })
    )
    expect(rows(wrapper)).toHaveLength(1)
    expect(rows(wrapper)[0].text()).toContain('Everyone')

    // The deleted link doesn't come back when searching afterwards.
    wrapper.findComponent(CrudTableSearch).vm.$emit('search-changed', '')
    await flushPromises()
    expect(rows(wrapper)).toHaveLength(1)
  })
})
