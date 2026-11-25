import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import { ModalStub } from '@baserow/test/helpers/modalStub'
import { BaserowPlugin } from '@baserow/modules/core/plugins'
import ImportWorkspaceModal from '@baserow/modules/core/components/import/ImportWorkspaceModal'

describe('ImportWorkspaceModal', () => {
  let testApp = null

  class ScopedIdentitiesPlugin extends BaserowPlugin {
    static getType() {
      return 'test_scoped_identities'
    }

    canCreateScopedIdentities(workspace) {
      return workspace.id === 1
    }
  }

  const groups = [
    { type: 'database', applications: [{ id: 4, name: 'CRM' }] },
    { type: 'agent', applications: [{ id: 3, name: 'Helper' }] },
  ]

  const mount = async (workspaceId, data) => {
    const wrapper = await testApp.mount(ImportWorkspaceModal, {
      props: { workspace: { id: workspaceId, name: 'Workspace' } },
      global: {
        stubs: {
          Modal: ModalStub,
          SelectedFileDetails: true,
          ImportApplicationSelector: true,
        },
      },
    })
    await wrapper.vm.show()
    await wrapper.setData({
      importFile: { name: 'export.zip', size: 1 },
      applicationGroups: groups,
      selectedApplicationIds: [3, 4],
      hasExportedIdentities: true,
      ...data,
    })
    return wrapper
  }

  const saysIdentitiesAreCreated = (wrapper) =>
    wrapper.find('.import-workspace__summary').exists()

  beforeEach(() => {
    testApp = new TestApp()
    testApp
      .getRegistry()
      .register('plugin', new ScopedIdentitiesPlugin({ app: testApp.getApp() }))
  })

  afterEach(async () => {
    testApp.getRegistry().unregister('plugin', ScopedIdentitiesPlugin.getType())
    await testApp.afterEach()
  })

  describe.each(['upload', 'import'])('while in the %s stage', (stage) => {
    test('says identities are created for a file that holds some', async () => {
      const wrapper = await mount(1, { currentStage: stage })

      expect(saysIdentitiesAreCreated(wrapper)).toBe(true)
    })

    test('says nothing for a file without identities', async () => {
      const wrapper = await mount(1, {
        currentStage: stage,
        hasExportedIdentities: false,
      })

      expect(saysIdentitiesAreCreated(wrapper)).toBe(false)
    })

    test('says nothing when no selected application can refer to one', async () => {
      const wrapper = await mount(1, {
        currentStage: stage,
        selectedApplicationIds: [4],
      })

      expect(saysIdentitiesAreCreated(wrapper)).toBe(false)
    })

    test('says nothing in a workspace the user cannot scope identities in', async () => {
      const wrapper = await mount(2, { currentStage: stage })

      expect(saysIdentitiesAreCreated(wrapper)).toBe(false)
    })
  })
})
