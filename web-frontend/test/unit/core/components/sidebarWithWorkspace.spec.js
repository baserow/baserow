import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import SidebarWithWorkspace from '@baserow/modules/core/components/sidebar/SidebarWithWorkspace'

describe('Workspace application sidebar groups', () => {
  let testApp, workspace, database, databaseType

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    workspace = testApp.store.getters['workspace/get'](1)
    database = await testApp.store.dispatch('application/forceCreate', {
      id: 10,
      type: 'database',
      name: 'Existing database',
      workspace: { id: 1 },
      tables: [],
    })
    databaseType = testApp.$registry.get('application', 'database')
    vi.spyOn(databaseType, 'canBeCreated').mockReturnValue(false)
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test('keeps visible applications navigable when their type cannot be created', async () => {
    const wrapper = await testApp.mount(SidebarWithWorkspace, {
      props: { applications: [database], selectedWorkspace: workspace },
    })
    const group = wrapper.find('[data-highlight="applications-database"]')
    expect(group.text()).toContain('Existing database')
    expect(
      wrapper
        .findAll('.tree__heading')
        .find((heading) => heading.text() === databaseType.getNamePlural())
        .find('.tree__heading-add')
        .exists()
    ).toBe(false)
  })

  test('omits non-creatable groups whose existing applications are hidden', async () => {
    vi.spyOn(databaseType, 'isVisible').mockReturnValue(false)
    const wrapper = await testApp.mount(SidebarWithWorkspace, {
      props: { applications: [database], selectedWorkspace: workspace },
    })
    expect(
      wrapper.find('[data-highlight="applications-database"]').exists()
    ).toBe(false)
    expect(
      wrapper.find('[data-highlight="applications-dashboard"]').exists()
    ).toBe(true)
  })
})
