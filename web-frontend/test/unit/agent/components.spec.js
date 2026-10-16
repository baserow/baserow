import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
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
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test('shows the application name and empty agent placeholder', async () => {
    const wrapper = await testApp.mount(AgentApplicationContent, {
      props: { agent },
    })
    expect(wrapper.find('h1').text()).toBe('Support agent')
    expect(wrapper.find('.agent-application__description').text()).toBe(
      'agent.emptyDescription'
    )
    expect(wrapper.find('button').exists()).toBe(false)

    await wrapper.setProps({ agent: { ...agent, name: 'Renamed agent' } })
    expect(wrapper.find('h1').text()).toBe('Renamed agent')
  })

  test('opens the application directly from its single sidebar row', async () => {
    const push = vi.spyOn(testApp.nuxtApp.$router, 'push').mockResolvedValue()
    const wrapper = await testApp.mount(AgentApplicationSidebar, {
      props: { application: agent, workspace: agent.workspace },
      global: {
        stubs: {
          SidebarApplication: {
            props: ['application'],
            template:
              '<li><button @click="$emit(\'selected\', application)">{{ application.name }}</button><slot name="body" /></li>',
          },
        },
      },
    })
    expect(wrapper.findAll('button')).toHaveLength(1)
    await wrapper.find('button').trigger('click')
    expect(push).toHaveBeenCalledWith({
      name: 'agent-application',
      params: { agentId: 10 },
    })
  })

  test('renames the agent through its standard application context', async () => {
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    const application = await testApp.store.dispatch(
      'application/forceCreate',
      agent
    )
    const workspace = testApp.store.getters['workspace/get'](1)
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
    testApp.mock.onPatch('/applications/10/').reply(200, {
      ...agent,
      name: 'Support assistant',
    })
    const wrapper = await testApp.mount(AgentApplicationSidebar, {
      props: { application, workspace },
    })
    await wrapper.find('.tree__options').trigger('click')
    await flushPromises()
    const rename = wrapper
      .findAll('.context__menu-item-link')
      .find((link) => link.text() === 'sidebarApplication.rename')
    await rename.trigger('click')
    const editable = wrapper.find('[contenteditable="true"]')
    expect(editable.exists()).toBe(true)
    editable.element.textContent = 'Support assistant'
    await editable.trigger('input')
    await editable.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(wrapper.find('.tree__link').attributes('aria-label')).toBe(
      'Support assistant'
    )
    expect(testApp.mock.history.patch).toHaveLength(1)
    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      name: 'Support assistant',
    })
  })
})
