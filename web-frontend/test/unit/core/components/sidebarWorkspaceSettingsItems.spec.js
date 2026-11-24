import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import SidebarMenu from '@baserow/modules/core/components/sidebar/SidebarMenu'
import { SettingsType } from '@baserow/modules/core/settingsTypes'
import { BaserowPlugin } from '@baserow/modules/core/plugins'

class IntegrationSettings extends SettingsType {
  static getType() {
    return 'test-integrations'
  }

  getName() {
    return 'Test integrations'
  }

  getIconClass() {
    return 'iconoir-puzzle'
  }

  getComponent() {
    return {
      props: ['workspace'],
      template: '<h2>Integrations for {{ workspace.name }}</h2>',
    }
  }
}

describe('Sidebar workspace settings tabs', () => {
  let app
  let integration

  beforeEach(() => {
    app = new TestApp()
    integration = new IntegrationSettings({ app: app.getApp() })
    app.$registry.register('workspaceSettings', integration)
  })

  afterEach(async () => {
    app.$registry.unregister('workspaceSettings', integration.type)
    await app.afterEach()
  })

  async function openSettings(canUpdate = true) {
    await app.store.dispatch('workspace/forceCreate', { id: 1, name: 'Design' })
    app.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    app.mock.onGet('/workspaces/1/roles/').reply(200, [])
    const wrapper = await app.mount(SidebarMenu, {
      props: { selectedWorkspace: app.store.getters['workspace/get'](1) },
      global: {
        mocks: {
          $hasPermission: (permission) =>
            permission !== 'workspace.update' || canUpdate,
        },
        stubs: { Teleport: false, NotificationPanel: true, InviteModal: true },
      },
    })
    await wrapper
      .get('[data-highlight="workspace-settings"] button')
      .trigger('click')
    await flushPromises()
    return app.body.get('.sidebar-workspace-menu:not(.visibility-hidden)')
  }

  test('opens the selected registry tab for the current workspace', async () => {
    const menu = await openSettings()
    expect(menu.text()).toContain('workspaceSettingType.aiProviders')
    const integrations = menu
      .findAll('button')
      .find((button) => button.text() === integration.getName())
    expect(integrations.find('.iconoir-puzzle').exists()).toBe(true)
    await integrations.trigger('click')
    const modal = app.body.get('.modal__wrapper')
    expect(modal.get('.modal-sidebar__nav-link.active').text()).toBe(
      integration.getName()
    )
    expect(modal.get('h2').text()).toBe('Integrations for Design')
  })

  test('shows the additional workspace context components', async () => {
    class PlanPlugin extends BaserowPlugin {
      static getType() {
        return 'test-plan'
      }

      getAdditionalWorkspaceContextComponents(workspace) {
        return [
          {
            props: ['workspace'],
            emits: ['hide'],
            template:
              '<li class="context__menu-item"><a class="context__menu-item-link test-plan" @click="$emit(\'hide\')">Plan of {{ workspace.name }}</a></li>',
          },
        ]
      }
    }
    const plugin = new PlanPlugin({ app: app.getApp() })
    app.$registry.register('plugin', plugin)
    try {
      const menu = await openSettings()
      const item = menu.get('.test-plan')
      expect(item.text()).toBe('Plan of Design')

      await item.trigger('click')
      await flushPromises()
      expect(
        app.body
          .find('.sidebar-workspace-menu:not(.visibility-hidden)')
          .exists()
      ).toBe(false)
    } finally {
      app.$registry.unregister('plugin', plugin.type)
    }
  })

  test('omits disabled tabs', async () => {
    vi.spyOn(integration, 'isEnabled').mockReturnValue(false)
    const menu = await openSettings()
    expect(menu.text()).toContain('workspaceSettingType.aiProviders')
    expect(menu.text()).not.toContain(integration.getName())
  })

  test('hides workspace settings tabs without workspace update permission', async () => {
    const menu = await openSettings(false)
    expect(menu.text()).not.toContain('workspaceSettingType.aiProviders')
    expect(menu.text()).not.toContain(integration.getName())
  })
})
