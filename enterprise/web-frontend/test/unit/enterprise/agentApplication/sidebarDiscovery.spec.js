import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import SidebarWithWorkspace from '@baserow/modules/core/components/sidebar/SidebarWithWorkspace'

describe('Agent application sidebar discovery', () => {
  let testApp, workspace

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    workspace = testApp.store.getters['workspace/get'](1)
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test('hides the Agent sidebar group and add controls when disabled', async () => {
    vi.spyOn(
      testApp.$registry.get('application', 'agent'),
      'canBeCreated'
    ).mockReturnValue(false)
    const existingAgent = await testApp.store.dispatch(
      'application/forceCreate',
      {
        id: 10,
        name: 'Existing Agent',
        type: 'agent',
        workspace: { id: 1 },
      }
    )
    const wrapper = await testApp.mount(SidebarWithWorkspace, {
      props: { applications: [existingAgent], selectedWorkspace: workspace },
    })

    expect(wrapper.find('[data-highlight="applications-agent"]').exists()).toBe(
      false
    )
    expect(
      wrapper.find('[data-highlight="applications-database"]').exists()
    ).toBe(true)
    expect(
      wrapper.find('[data-highlight="applications-dashboard"]').exists()
    ).toBe(true)
    await wrapper.find('.sidebar__new').trigger('click')
    const applicationNames = wrapper
      .findAll('.create-application-context .context__menu-item-title')
      .map((item) => item.text())
    expect(applicationNames).not.toContain('agentApplication.applicationName')
  })

  test('opens the single Agent creation form from its enabled sidebar group', async () => {
    const wrapper = await testApp.mount(SidebarWithWorkspace, {
      props: { applications: [], selectedWorkspace: workspace },
    })
    const heading = wrapper
      .findAll('.tree__heading')
      .find((item) => item.text() === 'agentApplication.applicationNamePlural')

    await heading.find('.tree__heading-add').trigger('click')
    expect(wrapper.findAll('.modal__wrapper')).toHaveLength(1)
    expect(wrapper.find('.modal__wrapper button').text()).toBe(
      'agentApplication.createApplication'
    )
    expect(wrapper.find('.modal__wrapper input').element.value).toBe(
      'agentApplication.applicationName'
    )
  })
})
