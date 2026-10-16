import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import SidebarWithWorkspace from '@baserow/modules/core/components/sidebar/SidebarWithWorkspace'

describe('SidebarWithWorkspace', () => {
  let testApp, workspace, databaseType

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    workspace = testApp.store.getters['workspace/get'](1)
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
    databaseType = testApp.$registry.get('application', 'database')
    vi.spyOn(databaseType, 'canBeCreated').mockReturnValue(false)
    vi.spyOn(databaseType, 'isVisible').mockReturnValue(true)
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test.each([
    [[], false],
    [[{ id: 2, name: 'Old', type: 'database', tables: [] }], true],
  ])(
    'shows a type that cannot be created only with existing applications %#',
    async (applications, shown) => {
      const wrapper = await testApp.mount(SidebarWithWorkspace, {
        props: {
          applications: applications.map((application) => ({
            ...application,
            workspace,
          })),
          selectedWorkspace: workspace,
        },
      })
      const heading = wrapper
        .findAll('.tree__heading')
        .find((item) => item.text() === databaseType.getNamePlural())

      expect(Boolean(heading)).toBe(shown)
      expect(heading?.find('.tree__heading-add').exists() ?? false).toBe(false)
    }
  )
})
