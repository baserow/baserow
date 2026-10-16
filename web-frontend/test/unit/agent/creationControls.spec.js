import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import SidebarWithWorkspace from '@baserow/modules/core/components/sidebar/SidebarWithWorkspace'

describe('Agent application creation controls', () => {
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

  test('does not offer Agent creation when disabled', async () => {
    vi.spyOn(
      testApp.$registry.get('application', 'agent'),
      'canBeCreated'
    ).mockReturnValue(false)
    const wrapper = await testApp.mount(SidebarWithWorkspace, {
      props: { applications: [], selectedWorkspace: workspace },
    })
    const heading = wrapper
      .findAll('.tree__heading')
      .find((item) => item.text() === 'agent.applicationNamePlural')
    expect(heading.find('.tree__heading-add').exists()).toBe(false)
    await wrapper.find('.sidebar__new').trigger('click')
    const applicationNames = wrapper
      .findAll('.create-application-context .context__menu-item-title')
      .map((item) => item.text())
    expect(applicationNames).not.toContain('agent.applicationName')
  })

  test('opens the single Agent creation form from its enabled sidebar group', async () => {
    const wrapper = await testApp.mount(SidebarWithWorkspace, {
      props: { applications: [], selectedWorkspace: workspace },
    })
    const heading = wrapper
      .findAll('.tree__heading')
      .find((item) => item.text() === 'agent.applicationNamePlural')

    await heading.find('.tree__heading-add').trigger('click')
    expect(wrapper.findAll('.modal__wrapper')).toHaveLength(1)
    expect(wrapper.find('.modal__wrapper button').text()).toBe(
      'agent.createApplication'
    )
    expect(wrapper.find('.modal__wrapper input').element.value).toBe(
      'agent.applicationName'
    )
  })
})
