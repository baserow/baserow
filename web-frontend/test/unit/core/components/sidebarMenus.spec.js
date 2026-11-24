import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import Sidebar from '@baserow/modules/core/components/sidebar/Sidebar.vue'

describe('Sidebar menu lifecycle', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountSidebar(options = {}) {
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Design',
    })
    const workspace = testApp.store.getters['workspace/get'](1)
    return testApp.mount(Sidebar, {
      ...options,
      props: {
        applications: [],
        workspaces: testApp.store.getters['workspace/getAll'],
        selectedWorkspace: workspace,
      },
      global: {
        stubs: {
          Teleport: false,
          SidebarMenu: true,
          SidebarWithWorkspace: true,
          SettingsModal: true,
        },
      },
    })
  }

  test('shows an empty state when the workspace search has no matches', async () => {
    const sidebar = await mountSidebar()
    await sidebar.get('.sidebar__workspace-trigger').trigger('click')
    await flushPromises()

    const picker = testApp.body.get('.sidebar-workspace-picker')
    const search = picker.get('input')
    await search.setValue('absent')
    expect(picker.get('[role="status"]').text()).toBe(
      'sidebar.noWorkspacesFound'
    )
    expect(picker.find('.sidebar-workspace-picker__item').exists()).toBe(false)

    await search.setValue('des')
    expect(picker.find('[role="status"]').exists()).toBe(false)
    expect(picker.get('.sidebar-workspace-picker__item').text()).toContain(
      'Design'
    )
  })

  test('marks only the pending workspace and allows retry after a failed switch', async () => {
    testApp.dontFailOnErrorResponses()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 2,
      name: 'Engineering',
    })
    const response = Promise.withResolvers()
    const url = '/workspaces/2/permissions/'
    testApp.mock.onGet(url).reply(() => response.promise)
    const sidebar = await mountSidebar()
    const trigger = sidebar.get('.sidebar__workspace-trigger')
    await trigger.trigger('click')
    await flushPromises()

    const options = testApp.body.findAll(
      'button.sidebar-workspace-picker__item'
    )
    const engineering = options.find((item) =>
      item.text().includes('Engineering')
    )
    const design = options.find((item) => item.text().includes('Design'))
    await engineering.trigger('click')
    expect(engineering.attributes('aria-busy')).toBe('true')
    expect(
      engineering.get('.sidebar-workspace-picker__loading').isVisible()
    ).toBe(true)
    expect(design.attributes('aria-busy')).toBeUndefined()
    await engineering.trigger('click')
    response.resolve([503, {}])
    await flushPromises()

    expect(trigger.attributes('aria-expanded')).toBe('true')
    expect(engineering.attributes('aria-disabled')).toBeUndefined()
    expect(
      engineering.find('.sidebar-workspace-picker__loading').exists()
    ).toBe(false)
    expect(
      testApp.mock.history.get.filter((request) => request.url === url)
    ).toHaveLength(1)
    await engineering.trigger('click')
    await flushPromises()
    expect(
      testApp.mock.history.get.filter((request) => request.url === url)
    ).toHaveLength(2)
  })

  test.each(['open', 'opening'])(
    'closing the workspace picker also closes %s row actions',
    async (state) => {
      testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
      const sidebar = await mountSidebar()
      const workspace = testApp.store.getters['workspace/get'](1)
      await testApp.store.dispatch('workspace/fetchPermissions', workspace)
      await testApp.store.dispatch('workspace/fetchRoles', workspace)
      const trigger = sidebar.get('.sidebar__workspace-trigger')
      await trigger.trigger('click')
      await flushPromises()

      const actions = testApp.body.get('.sidebar-workspace-picker__actions')
      actions.element.click()
      if (state === 'open') {
        await flushPromises()
        expect(actions.attributes('aria-expanded')).toBe('true')
      }

      const search = testApp.body.get('.sidebar-workspace-picker input')
      search.element.focus()
      await search.trigger('keydown', { key: 'Escape' })
      await flushPromises()

      expect(trigger.attributes('aria-expanded')).toBe('false')
      expect(actions.attributes('aria-expanded')).toBe('false')
      expect(document.activeElement).toBe(trigger.element)
    }
  )

  test('reopens the admin sidebar when selecting the current admin page', async () => {
    testApp.mock.onGet('/settings/').reply(200, {})
    testApp.mock.onGet('/workspaces/').reply(200, [{ id: 1, name: 'Design' }])
    testApp.mock.onGet('/applications/').reply(200, [])
    testApp.authenticate({
      id: 1,
      first_name: 'Ada Lovelace',
      username: 'ada@example.com',
      is_staff: true,
    })
    const sidebar = await mountSidebar({ route: '/admin/dashboard' })
    expect(sidebar.find('.sidebar__title').exists()).toBe(true)

    await sidebar.get('.sidebar__back').trigger('click')
    expect(sidebar.find('.sidebar__workspace-trigger').exists()).toBe(true)

    const account = sidebar.get('.sidebar__account-trigger')
    await account.trigger('click')
    await flushPromises()
    await testApp.body
      .get('.sidebar-account-menu button[aria-expanded]')
      .trigger('click')
    await flushPromises()
    const adminLink = testApp.body.get(
      '.sidebar-admin-menu a[href="/admin/dashboard"]'
    )
    await adminLink.trigger('click', { ctrlKey: true })
    await flushPromises()
    expect(account.attributes('aria-expanded')).toBe('true')

    await adminLink.trigger('click')
    await flushPromises()

    expect(sidebar.find('.sidebar__title').exists()).toBe(true)
    expect(
      testApp.body
        .find('.sidebar-account-menu:not(.visibility-hidden)')
        .exists()
    ).toBe(false)
  })
})
