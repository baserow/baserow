import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import WorkspaceSettingsModal from '@baserow/modules/core/components/workspace/WorkspaceSettingsModal'
import { SettingsType } from '@baserow/modules/core/settingsTypes'

const workspace = { id: 1, name: 'Acme', _: { roles: [] } }

function settingsType(type, order, enabledFor) {
  return new (class extends SettingsType {
    static getType() {
      return type
    }

    getIconClass() {
      return 'iconoir-settings'
    }

    getName() {
      return type
    }

    getOrder() {
      return order
    }

    getComponent() {
      return { name: type, template: `<div class="page-${type}" />` }
    }

    isEnabled(forWorkspace) {
      return enabledFor(forWorkspace)
    }
  })()
}

describe('WorkspaceSettingsModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    const registry = testApp.getRegistry()
    for (const type of Object.keys(registry.getAll('workspaceSettings'))) {
      registry.unregister('workspaceSettings', type)
    }
    registry.register(
      'workspaceSettings',
      settingsType('hidden', 10, () => false)
    )
    registry.register(
      'workspaceSettings',
      settingsType('own', 20, (forWorkspace) => forWorkspace?.id === 1)
    )
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('only lists and opens the pages enabled for the workspace', async () => {
    const wrapper = await testApp.mount(WorkspaceSettingsModal, {
      props: { workspace },
    })
    await wrapper.vm.show()
    await flushPromises()

    const names = wrapper
      .findAll('.modal-sidebar__nav-link')
      .map((link) => link.text())
    expect(names).toEqual(['own'])
    expect(wrapper.vm.page).toBe('own')
  })
})
