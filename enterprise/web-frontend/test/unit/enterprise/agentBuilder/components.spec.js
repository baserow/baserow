import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentBuilderContent from '@baserow_enterprise/agentBuilder/components/AgentBuilderContent'

describe('Agent Builder content', () => {
  let testApp
  const agentBuilder = {
    id: 10,
    name: 'Support team',
    type: 'agent_builder',
    workspace: { id: 1 },
    agents: [{ id: 11, name: 'Support agent' }],
  }

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test('shows the empty agent honestly and uses the selected ID', async () => {
    await testApp.store.dispatch('agentBuilderAgent/select', 11)
    const wrapper = await testApp.mount(AgentBuilderContent, {
      props: { agentBuilder },
      global: { stubs: { CreateAgentModal: true } },
    })
    expect(wrapper.find('h1').text()).toBe('Support agent')
    expect(wrapper.find('.agent-builder__description').text()).toBe(
      'agentBuilder.agentDescription'
    )
  })

  test('switches between named agents using their IDs', async () => {
    const wrapper = await testApp.mount(AgentBuilderContent, {
      props: {
        agentBuilder: {
          ...agentBuilder,
          agents: [...agentBuilder.agents, { id: 12, name: 'Sales agent' }],
        },
      },
      global: { stubs: { CreateAgentModal: true } },
    })
    expect(wrapper.find('h1').text()).toBe('agentBuilder.emptyTitle')
    await testApp.store.dispatch('agentBuilderAgent/select', 11)
    expect(wrapper.find('h1').text()).toBe('Support agent')
    await testApp.store.dispatch('agentBuilderAgent/select', 12)
    expect(wrapper.find('h1').text()).toBe('Sales agent')
  })
})
