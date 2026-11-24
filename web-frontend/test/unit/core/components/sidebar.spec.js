import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import Sidebar from '@baserow/modules/core/components/sidebar/Sidebar.vue'
import SidebarAllWorkspaces from '@baserow/modules/core/components/sidebar/SidebarAllWorkspaces.vue'
import SidebarFoot from '@baserow/modules/core/components/sidebar/SidebarFoot.vue'
import SidebarMenu from '@baserow/modules/core/components/sidebar/SidebarMenu.vue'

describe('Workspace sidebar', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('keeps the collapsed breadcrumb picker keyboard accessible', async () => {
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Design',
    })
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 2,
      name: 'Engineering',
    })
    const workspaces = testApp.store.getters['workspace/getAll']
    const wrapper = await testApp.mount(Sidebar, {
      props: {
        applications: [],
        workspaces,
        selectedWorkspace: workspaces.find(({ id }) => id === 1),
        collapsed: true,
        width: 52,
      },
      global: {
        stubs: {
          SidebarWithWorkspace: true,
          SidebarMenu: true,
          SidebarFoot: true,
        },
      },
    })

    const home = wrapper.get('a[href="/all-workspaces"]')
    const switcher = wrapper.get('button[aria-label="Design"]')
    expect(home.isVisible()).toBe(true)
    expect(switcher.isVisible()).toBe(true)

    await switcher.trigger('click')
    await flushPromises()

    expect(switcher.attributes('aria-expanded')).toBe('true')
    expect(document.activeElement?.getAttribute('placeholder')).toBe(
      'action.search'
    )
    const picker = document.querySelector('.sidebar-workspace-picker')
    expect(picker.querySelector('[aria-current="true"]').textContent).toContain(
      'Design'
    )
    expect(picker.textContent).toContain('Engineering')
    expect(picker.textContent).not.toContain('sidebar.settings')

    const search = testApp.body.get('input[aria-label="action.search"]')
    expect(document.activeElement).toBe(search.element)

    const [design, engineering] = testApp.body.findAll(
      '[data-workspace-option]'
    )
    await search.trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(design.element)
    await design.trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(engineering.element)
    await engineering.trigger('keydown', { key: 'Home' })
    expect(document.activeElement).toBe(design.element)
    await design.trigger('keydown', { key: 'ArrowUp' })
    expect(document.activeElement).toBe(search.element)

    await search.setValue('engineer')
    const filteredOption = testApp.body.get('[data-workspace-option]')
    expect(filteredOption.text()).toContain('Engineering')
    await search.trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(filteredOption.element)
    await filteredOption.trigger('keydown', { key: 'Escape' })
    expect(switcher.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(switcher.element)
  })

  test('shows the logo link and keeps workspace notifications off the account menu', async () => {
    testApp.store.commit('notification/SET_PER_WORKSPACE_UNREAD_COUNT', {
      1: 2,
    })
    const wrapper = await testApp.mount(SidebarAllWorkspaces, {
      props: { selectedWorkspace: {} },
      global: {
        stubs: {
          SidebarAllWorkspacesMenu: true,
          SidebarAccountMenu: true,
        },
      },
    })

    const account = wrapper.get('.sidebar__account-trigger')
    expect(account.find('.sidebar__unread-notifications-icon').exists()).toBe(
      false
    )
    const brand = wrapper.get('a.sidebar__brand')
    expect(brand.attributes('href')).toBe('/all-workspaces')
    expect(brand.get('img').isVisible()).toBe(true)
    expect(
      wrapper.findComponent({ name: 'SidebarWorkspacePicker' }).exists()
    ).toBe(false)
  })

  test('opens workspace settings and help and restores focus', async () => {
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Design',
    })
    const workspace = testApp.store.getters['workspace/get'](1)
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
    await testApp.store.dispatch('workspace/fetchPermissions', workspace)
    await testApp.store.dispatch('workspace/fetchRoles', workspace)
    const wrapper = await testApp.mount(SidebarMenu, {
      props: { selectedWorkspace: workspace },
      global: {
        mocks: { $hasPermission: () => true },
        stubs: {
          Teleport: false,
          NotificationPanel: true,
          InviteModal: true,
          WorkspaceSettingsModal: true,
        },
      },
    })

    const [settings, help] = wrapper.findAll('button[aria-expanded]')
    expect(settings.text()).toBe('sidebar.workspaceSettings')
    expect(help.text()).toBe('sidebar.help')

    await settings.trigger('click')
    await flushPromises()
    const settingsMenu = testApp.body.get(
      '.sidebar-workspace-menu:not(.visibility-hidden)'
    )
    expect(settings.attributes('aria-expanded')).toBe('true')
    expect(document.activeElement.textContent.trim()).toBe(
      'sidebar.inviteOthers'
    )
    expect(
      settingsMenu.get('a[href="/workspace/1/settings/members"]').text()
    ).toBe('workspaceContext.members')

    await help.trigger('click')
    await flushPromises()
    expect(settings.attributes('aria-expanded')).toBe('false')
    expect(help.attributes('aria-expanded')).toBe('true')
    const helpMenu = testApp.body.get(
      '.sidebar-workspace-menu:not(.visibility-hidden)'
    )
    const knowledgeBase = helpMenu.get('a[href="https://baserow.io/user-docs"]')
    const firstHelpItem = helpMenu.get('.context__menu-item-link')
    expect(document.activeElement).toBe(firstHelpItem.element)
    expect(knowledgeBase.text()).toBe('sidebar.knowledgeBase')
    expect(helpMenu.get('a[href="https://academy.baserow.io/"]').text()).toBe(
      'dashboard.academy'
    )
    expect(
      helpMenu
        .get('a[href="https://baserow.io/blog/category/tutorials"]')
        .text()
    ).toBe('dashboard.tutorials')
    expect(helpMenu.get('a[href="/api-docs"]').text()).toBe(
      'sidebar.apiDocumentation'
    )

    await firstHelpItem.trigger('keydown', { key: 'Escape' })
    expect(help.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(help.element)
  })

  test.each([true, false])(
    'links to the workspace integrations from the settings menu only when they may be listed (%s)',
    async (canListIntegrations) => {
      await testApp.store.dispatch('workspace/forceCreate', {
        id: 1,
        name: 'Design',
      })
      testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
      testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
      const wrapper = await testApp.mount(SidebarMenu, {
        props: { selectedWorkspace: testApp.store.getters['workspace/get'](1) },
        global: {
          mocks: {
            $hasPermission: (permission) =>
              permission !== 'workspace.list_integrations' ||
              canListIntegrations,
          },
          stubs: {
            Teleport: false,
            NotificationPanel: true,
            InviteModal: true,
            WorkspaceSettingsModal: true,
          },
        },
      })

      await wrapper
        .get('[data-highlight="workspace-settings"] button')
        .trigger('click')
      await flushPromises()
      const link = testApp.body
        .get('.sidebar-workspace-menu:not(.visibility-hidden)')
        .find('a[href="/workspace/1/settings/integrations"]')
      expect(link.exists()).toBe(canListIntegrations)
      if (canListIntegrations) {
        expect(link.text()).toBe('workspaceIntegrations.tabTitle')
      }
    }
  )

  test('discards workspace actions when the selected workspace changes', async () => {
    const { store, mock } = testApp
    for (const [id, name] of [
      [1, 'Design'],
      [2, 'Engineering'],
    ]) {
      await store.dispatch('workspace/forceCreate', { id, name })
      const workspace = store.getters['workspace/get'](id)
      mock.onGet(`/workspaces/${id}/permissions/`).reply(200, [])
      mock.onGet(`/workspaces/${id}/roles/`).reply(200, [])
      await store.dispatch('workspace/fetchPermissions', workspace)
      await store.dispatch('workspace/fetchRoles', workspace)
    }
    const design = store.getters['workspace/get'](1)
    const engineering = store.getters['workspace/get'](2)
    const wrapper = await testApp.mount(SidebarMenu, {
      props: { selectedWorkspace: design },
      global: {
        mocks: { $hasPermission: () => true },
        stubs: {
          Teleport: false,
          NotificationPanel: true,
          InviteModal: true,
          WorkspaceSettingsModal: true,
        },
      },
    })
    const settings = wrapper.get('[data-highlight="workspace-settings"] button')
    const visibleMenu = '.sidebar-workspace-menu:not(.visibility-hidden)'

    await settings.trigger('click')
    await flushPromises()
    expect(
      testApp.body
        .get(visibleMenu)
        .get('a[href="/workspace/1/settings/members"]')
        .exists()
    ).toBe(true)

    await wrapper.setProps({ selectedWorkspace: engineering })
    expect(settings.attributes('aria-expanded')).toBe('false')
    expect(testApp.body.find(visibleMenu).exists()).toBe(false)

    await settings.trigger('click')
    await flushPromises()
    const menu = testApp.body.get(visibleMenu)
    expect(menu.get('a[href="/workspace/2/settings/members"]').exists()).toBe(
      true
    )
    const rename = menu
      .findAll('button')
      .find((button) => button.text() === 'workspaceContext.renameWorkspace')
    await rename.trigger('click')
    await flushPromises()
    const modal = testApp.body.get('.modal__wrapper')
    expect(modal.get('input').element.value).toBe('Engineering')

    await wrapper.setProps({ selectedWorkspace: design })
    expect(testApp.body.find('.modal__wrapper').exists()).toBe(false)
  })

  test('only deletes the workspace after confirmation and offers to restore it', async () => {
    const { store, mock, body } = testApp
    await store.dispatch('workspace/forceCreate', { id: 1, name: 'Design' })
    const workspace = store.getters['workspace/get'](1)
    mock.onGet('/workspaces/1/permissions/').reply(200, [])
    mock.onGet('/workspaces/1/roles/').reply(200, [])
    mock.onDelete('/workspaces/1/').reply(204)
    const wrapper = await testApp.mount(SidebarMenu, {
      props: { selectedWorkspace: workspace },
      global: {
        mocks: { $hasPermission: () => true },
        stubs: { Teleport: false, NotificationPanel: true },
      },
    })
    const settings = wrapper.get('[data-highlight="workspace-settings"] button')
    async function openDeletePrompt() {
      await settings.trigger('click')
      await flushPromises()
      await body
        .get('.sidebar-workspace-menu .context__menu-item-link--delete')
        .trigger('click')
      return body.get('.modal__wrapper')
    }

    const prompt = await openDeletePrompt()
    await prompt.get('.action__links a').trigger('click')
    await expect.poll(() => body.find('.modal__wrapper').exists()).toBe(false)
    expect(mock.history.delete).toHaveLength(0)

    const reopenedPrompt = await openDeletePrompt()
    await reopenedPrompt.get('button.button--danger').trigger('click')
    await flushPromises()
    expect(mock.history.delete.map(({ url }) => url)).toEqual([
      '/workspaces/1/',
    ])
    expect(store.state.toast.items).toContainEqual(
      expect.objectContaining({
        type: 'restore',
        data: { trash_item_type: 'workspace', trash_item_id: 1 },
      })
    )
  })

  test('restores focus one level at a time when closing the admin submenu', async () => {
    testApp.authenticate({
      id: 1,
      first_name: 'Ada Lovelace',
      username: 'ada@example.com',
      is_staff: true,
    })
    const wrapper = await testApp.mount(SidebarFoot, {
      props: { selectedWorkspace: {}, width: 240 },
      global: {
        stubs: {
          Teleport: false,
          SettingsModal: true,
          SidebarAdmin: {
            template: '<a href="/admin/dashboard">Dashboard</a>',
          },
        },
      },
    })

    const account = wrapper.get('button[aria-label="Ada Lovelace"]')
    await account.trigger('click')
    await flushPromises()
    expect(account.attributes('aria-expanded')).toBe('true')
    expect(document.activeElement?.textContent.trim()).toBe('sidebar.settings')

    const admin = testApp.body.get(
      '.sidebar-account-menu button[aria-expanded]'
    )
    await admin.trigger('click')
    await flushPromises()
    const dashboard = testApp.body.get('.sidebar-admin-menu a')
    expect(admin.attributes('aria-expanded')).toBe('true')
    expect(document.activeElement).toBe(dashboard.element)

    await dashboard.trigger('keydown', { key: 'Escape' })
    expect(admin.attributes('aria-expanded')).toBe('false')
    expect(account.attributes('aria-expanded')).toBe('true')
    expect(document.activeElement).toBe(admin.element)

    await admin.trigger('keydown', { key: 'Escape' })
    expect(account.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(account.element)
  })
})
