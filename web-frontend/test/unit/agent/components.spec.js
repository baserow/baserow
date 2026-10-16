import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentApplicationContent from '@baserow/modules/agent/components/AgentApplicationContent'
import AgentApplicationSidebar from '@baserow/modules/agent/components/AgentApplicationSidebar'

describe('Agent application components', () => {
  let testApp
  const agent = {
    id: 10,
    name: 'Support agent',
    type: 'agent',
    workspace: { id: 1 },
  }

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('shows the Agent name and toggles its configuration', async () => {
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    testApp.mock.onGet('/workspaces/').reply(200, [{ id: 1 }])
    testApp.mock
      .onGet('/agent/10/readiness/')
      .reply(200, { state: 'incomplete' })
    testApp.mock.onGet('/agent/10/configuration/').reply(200, {
      name: agent.name,
      instructions: '',
      provider_type: null,
      model_identifier: null,
      state: 'incomplete',
      errors: { instructions: 'required' },
    })
    const wrapper = await testApp.mount(AgentApplicationContent, {
      props: { agent },
    })
    expect(wrapper.find('.agent-application__header-name').text()).toBe(
      'Support agent'
    )
    expect(wrapper.find('h1').text()).toContain('Support agent')
    const configuration = wrapper.get(
      'button[aria-label="agent.configuration"]'
    )
    expect(configuration.text()).toBe('')
    expect(configuration.attributes('aria-expanded')).toBe('true')
    await configuration.trigger('click')
    expect(wrapper.find('.agent-configuration').exists()).toBe(false)
    expect(configuration.attributes('aria-expanded')).toBe('false')
    await configuration.trigger('click')
    expect(wrapper.find('.agent-configuration').exists()).toBe(true)
  })

  test('renames the agent through the standard application context', async () => {
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    const application = await testApp.store.dispatch(
      'application/forceCreate',
      agent
    )
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
    testApp.mock
      .onPatch('/applications/10/')
      .reply(200, { ...agent, name: 'Support assistant' })
    const wrapper = await testApp.mount(AgentApplicationSidebar, {
      props: {
        application,
        workspace: testApp.store.getters['workspace/get'](1),
      },
    })

    await wrapper.find('.tree__options').trigger('click')
    await flushPromises()
    await wrapper
      .findAll('.context__menu-item-link')
      .find((link) => link.text() === 'sidebarApplication.rename')
      .trigger('click')
    const editable = wrapper.find('[contenteditable="true"]')
    editable.element.textContent = 'Support assistant'
    await editable.trigger('input')
    await editable.trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      name: 'Support assistant',
    })
    expect(wrapper.find('.tree__link').attributes('aria-label')).toBe(
      'Support assistant'
    )
  })
})
