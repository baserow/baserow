import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import Sidebar from '@baserow/modules/core/components/sidebar/Sidebar.vue'
import SidebarAllWorkspaces from '@baserow/modules/core/components/sidebar/SidebarAllWorkspaces.vue'
import SidebarFoot from '@baserow/modules/core/components/sidebar/SidebarFoot.vue'

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

  test('shows the logo link above the All Workspaces menu', async () => {
    const wrapper = await testApp.mount(SidebarAllWorkspaces, {
      props: { selectedWorkspace: {} },
      global: {
        stubs: {
          SidebarAllWorkspacesMenu: true,
          SidebarFoot: true,
        },
      },
    })

    const brand = wrapper.get('a.sidebar__brand')
    expect(brand.attributes('href')).toBe('/all-workspaces')
    expect(brand.get('img').isVisible()).toBe(true)
    expect(wrapper.findComponent({ name: 'SidebarUserContext' }).exists()).toBe(
      false
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
