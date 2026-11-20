import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import { AgentApplicationType } from '@baserow/modules/agent/applicationTypes'
import AgentTemplate from '@baserow/modules/agent/components/AgentTemplate'
import AgentTemplateSidebar from '@baserow/modules/agent/components/AgentTemplateSidebar'
import { agentData, completeConfiguration, periodicTrigger } from './helpers'

describe('Agent template preview', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('the agent type opens a template page for each agent', () => {
    const type = new AgentApplicationType({
      app: { $featureFlagIsEnabled: () => true },
    })
    const agent = { ...agentData }

    expect(type.getTemplateSidebarComponent()).toBe(AgentTemplateSidebar)
    expect(type.getTemplatesPageComponent()).toBe(AgentTemplate)
    expect(type.getTemplatePage(agent)).toEqual({ agent })
  })

  test('the agent type leaves agents out of a template without the flag', () => {
    const type = new AgentApplicationType({
      app: { $featureFlagIsEnabled: () => false },
    })

    expect(type.getTemplateSidebarComponent()).toBeNull()
    expect(type.getTemplatePage({ ...agentData })).toBeNull()
  })

  test('selecting the agent in the template sidebar opens its page', async () => {
    const agent = { ...agentData, _: { selected: false, type: {} } }
    const wrapper = await testApp.mount(AgentTemplateSidebar, {
      props: { application: agent, page: null },
    })

    await wrapper.get('.tree__link').trigger('click')

    expect(wrapper.emitted('selected')).toEqual([[agent]])
    expect(wrapper.emitted('selected-page')).toEqual([
      [{ application: 'agent', value: { agent } }],
    ])
  })

  const mountTemplate = () => {
    testApp.mock.onGet('/agent/10/configuration/').reply(
      200,
      completeConfiguration({
        instructions: 'Answer support questions.',
        run_as: null,
        pending_tools: ['list_tables'],
        available_tools: [
          { name: 'list_tables', group: 'database', changes_data: false },
        ],
      })
    )
    testApp.mock
      .onGet('/agent/10/triggers/')
      .reply(200, [periodicTrigger({ name: 'Morning digest' })])
    testApp.mock
      .onGet('/agent/10/actions/')
      .reply(200, [{ id: 3, type: 'smtp_email', name: 'Notify the team' }])
    testApp.mock.onGet('application/10/integrations/').reply(200, [
      { id: 4, type: 'mcp_server', name: 'Docs' },
      { id: 5, type: 'smtp', name: 'Mail server' },
    ])
    return testApp.mount(AgentTemplate, {
      props: { pageValue: { agent: { ...agentData } } },
    })
  }

  test('shows the agent setup read-only', async () => {
    const wrapper = await mountTemplate()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Support agent')
    expect(text).toContain('Answer support questions.')
    expect(text).toContain('model-one')
    expect(text).toContain('Morning digest')
    expect(text).toContain('Notify the team')
    expect(text).toContain('Docs')
    // Only MCP servers are connected apps; the rest belong to actions.
    expect(text).not.toContain('Mail server')
    expect(wrapper.findAll('input, textarea, button')).toHaveLength(0)
  })

  test('reads only what a template preview may read', async () => {
    await mountTemplate()
    await flushPromises()

    const urls = testApp.mock.history.get.map(({ url }) => url)
    expect(urls.sort()).toEqual(
      [
        '/agent/10/actions/',
        '/agent/10/configuration/',
        '/agent/10/triggers/',
        'application/10/integrations/',
      ].sort()
    )
    expect(testApp.mock.history.post).toHaveLength(0)
    expect(testApp.mock.history.patch).toHaveLength(0)
  })
})
