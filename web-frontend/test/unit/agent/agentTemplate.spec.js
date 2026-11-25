import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import { AgentApplicationType } from '@baserow/modules/agent/applicationTypes'
import AgentTemplate from '@baserow/modules/agent/components/AgentTemplate'
import AgentTemplateSidebar from '@baserow/modules/agent/components/AgentTemplateSidebar'
import {
  agentData,
  completeConfiguration,
  conversation,
  conversationsPage,
  message,
  messages,
  mockConfiguration,
  mockConversations,
  mockMessages,
  openSection,
  page,
  periodicTrigger,
} from './helpers'

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

  const templateConfiguration = () =>
    completeConfiguration({
      instructions: 'Answer support questions.',
      run_as: null,
      allowed_tools: [],
      ask_first_tools: [],
      pending_tools: ['list_tables', 'create_rows'],
      pending_ask_first_tools: ['create_rows'],
      available_tools: [
        { name: 'list_tables', group: 'database', changes_data: false },
        { name: 'create_rows', group: 'database', changes_data: true },
      ],
      // The model is checked against the template's own workspace.
      readiness: 'unavailable',
      errors: { model_identifier: 'unavailable' },
    })

  const mountTemplate = async ({ conversations = [] } = {}) => {
    mockConfiguration(testApp, templateConfiguration())
    mockConversations(testApp, conversationsPage(conversations))
    testApp.mock
      .onGet('/agent/10/triggers/')
      .reply(200, [periodicTrigger({ name: 'Morning digest' })])
    testApp.mock.onGet('/agent/10/actions/').reply(200, [
      {
        id: 3,
        type: 'smtp_email',
        name: 'Notify the team',
        description: '',
        inputs: [],
        enabled: true,
        ask_first: true,
        service: { id: 7, type: 'smtp_email', integration_id: 5 },
      },
    ])
    testApp.mock.onGet('application/10/integrations/').reply(200, [
      { id: 4, type: 'mcp_server', name: 'Docs', tools: [] },
      { id: 5, type: 'smtp', name: 'Mail server' },
    ])
    const wrapper = await testApp.mount(AgentTemplate, {
      props: { pageValue: { agent: { ...agentData, integrations: [] } } },
    })
    await flushPromises()
    return wrapper
  }

  const requests = (method = 'get') =>
    testApp.mock.history[method].map(({ url }) => url).sort()

  test('shows the agent like its page, without a way to chat', async () => {
    const wrapper = await mountTemplate()

    expect(wrapper.get('.agent-application__header-name').text()).toBe(
      'Support agent'
    )
    expect(wrapper.get('.agent-chat__intro').text()).toContain('Support agent')
    expect(wrapper.get('.agent-chat__footer').text()).toBe(
      'agent.templatePreviewHint'
    )
    expect(wrapper.find('.agent-chat__composer').exists()).toBe(false)
    expect(wrapper.find('.agent-conversations').exists()).toBe(false)
    expect(wrapper.find('.agent-application__approvals').exists()).toBe(false)
    // The template's workspace decides nothing about the visitor's models.
    expect(wrapper.find('.agent-chat__warning').exists()).toBe(false)
    expect(
      wrapper.find('.agent-configuration__section-status.icon--error').exists()
    ).toBe(false)
    expect(
      wrapper.findAll('.agent-configuration .menu-list__item-button')
    ).toHaveLength(7)
  })

  test('shows the configuration sections read-only', async () => {
    const wrapper = await mountTemplate()

    await openSection(wrapper, 'agent.instructions')
    const instructions = wrapper.get('.agent-configuration textarea')
    expect(instructions.element.value).toBe('Answer support questions.')
    expect(instructions.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.read-only-form').exists()).toBe(true)

    await wrapper.get('.agent-configuration__header-button').trigger('click')
    await openSection(wrapper, 'agent.whenItRuns')
    await flushPromises()
    expect(wrapper.get('.agent-trigger-card__name').element.value).toBe(
      'Morning digest'
    )
    expect(wrapper.find('.agent-triggers__add').exists()).toBe(false)
    expect(wrapper.find('.agent-trigger-card__delete').exists()).toBe(false)
    expect(wrapper.find('.agent-trigger-card__status').exists()).toBe(false)

    await wrapper.get('.agent-configuration__header-button').trigger('click')
    await openSection(wrapper, 'agent.actions')
    await flushPromises()
    expect(wrapper.get('.agent-action-card__title').text()).toBe(
      'Notify the team'
    )
    expect(wrapper.find('.agent-action-card__footer').exists()).toBe(false)

    await wrapper.get('.agent-configuration__header-button').trigger('click')
    await openSection(wrapper, 'agent.connectedApps')
    await flushPromises()
    const apps = wrapper.get('.agent-connected-apps').text()
    expect(apps).toContain('Docs')
    // Only MCP servers are connected apps; the rest belong to actions.
    expect(apps).not.toContain('Mail server')
    expect(wrapper.find('.agent-connected-apps__add').exists()).toBe(false)
  })

  test('shows the tools the agent turns on once it is installed', async () => {
    const wrapper = await mountTemplate()

    await openSection(wrapper, 'agent.workspaceAccess')
    await flushPromises()

    const section = wrapper.get('.agent-configuration__body')
    expect(section.text()).toContain('agent.templatePreviewIdentity')
    expect(section.text()).not.toContain('agent.toolsRequireIdentity')
    const tools = section.get('.agent-workspace-tools__switch')
    expect(tools.attributes('aria-checked')).toBe('true')
    expect(tools.attributes('aria-disabled')).toBe('true')
    const group = section.get('.agent-workspace-tools__group').text()
    expect(group).toContain('agent.toolsSummary')
    // Pending tools that change data ask first once installed.
    expect(group).toContain('agent.toolsAskCount')
  })

  test('reads only what a template preview may read', async () => {
    const wrapper = await mountTemplate()

    expect(requests()).toEqual([
      '/agent/10/configuration/',
      '/agent/10/conversations/',
    ])

    for (const section of [
      'agent.whenItRuns',
      'agent.workspaceAccess',
      'agent.actions',
      'agent.connectedApps',
      'agent.agentSettings',
    ]) {
      await openSection(wrapper, section)
      await flushPromises()
      await wrapper.get('.agent-configuration__header-button').trigger('click')
    }

    // Not the trigger types or the identities, which need a workspace member.
    expect([...new Set(requests())]).toEqual([
      '/agent/10/actions/',
      '/agent/10/configuration/',
      '/agent/10/conversations/',
      '/agent/10/triggers/',
      'application/10/integrations/',
    ])
    for (const method of ['post', 'patch', 'put', 'delete']) {
      expect(requests(method)).toEqual([])
    }
  })

  test('shows no conversations when they cannot be read', async () => {
    mockConfiguration(testApp, templateConfiguration())
    mockConversations(testApp, [401, { error: 'PERMISSION_DENIED' }])
    const wrapper = await testApp.mount(AgentTemplate, {
      props: { pageValue: { agent: { ...agentData, integrations: [] } } },
    })
    await flushPromises()

    expect(wrapper.find('.agent-conversations').exists()).toBe(false)
    expect(wrapper.find('.alert').exists()).toBe(false)
    expect(wrapper.find('.agent-chat__intro').exists()).toBe(true)
    expect(
      wrapper.findAll('.agent-configuration .menu-list__item-button')
    ).toHaveLength(7)
  })

  test('shows the example conversations read-only', async () => {
    mockMessages(
      testApp,
      'first',
      page([
        message('question', 'Where is my order?', { id: 1 }),
        message('answer', 'It ships tomorrow.', {
          id: 2,
          role: 'assistant',
          status: 'completed',
        }),
      ])
    )
    mockMessages(
      testApp,
      'second',
      page([message('other', 'Can I get a refund?', { id: 3 })])
    )
    const wrapper = await mountTemplate({
      conversations: [
        { ...conversation('first', 'Order status'), shared: true },
        { ...conversation('second', 'Refund'), shared: true },
      ],
    })

    expect(
      wrapper
        .findAll('.agent-conversations__item-name')
        .map((item) => item.text())
    ).toEqual(['Order status', 'Refund'])
    expect(
      wrapper.get('.agent-conversations__item[aria-current="true"]').text()
    ).toContain('Order status')
    // A visitor sees who wrote each message of the example.
    expect(messages(wrapper)).toEqual([
      'ViewerWhere is my order?',
      'It ships tomorrow.',
    ])
    expect(wrapper.find('.agent-chat__intro').exists()).toBe(false)
    expect(wrapper.find('.agent-chat__composer').exists()).toBe(false)
    expect(wrapper.find('.agent-conversations__options').exists()).toBe(false)
    expect(wrapper.find('.agent-conversations__footer').exists()).toBe(false)
    expect(wrapper.get('.agent-chat__footer').text()).toBe(
      'agent.templatePreviewHint'
    )

    await wrapper
      .findAll('.agent-conversations__item')
      .find((item) => item.text().includes('Refund'))
      .trigger('click')
    await flushPromises()

    expect(messages(wrapper)).toEqual(['ViewerCan I get a refund?'])
    expect(requests('post')).toEqual([])
    expect(requests('patch')).toEqual([])
  })

  const mountPreview = async () => {
    const wrapper = await testApp.mount(AgentTemplate, {
      props: { pageValue: { agent: { ...agentData, integrations: [] } } },
    })
    await flushPromises()
    return wrapper
  }

  test('offers to load the conversations again when that failed', async () => {
    mockConfiguration(testApp, templateConfiguration())
    mockConversations(
      testApp,
      [500, {}],
      conversationsPage([
        { ...conversation('first', 'Order status'), shared: true },
      ])
    )
    mockMessages(
      testApp,
      'first',
      page([message('user', 'Where is my order?', { id: 1 })])
    )
    const wrapper = await mountPreview()

    expect(wrapper.find('.agent-chat__intro').exists()).toBe(false)
    await wrapper.get('.agent-conversations .alert .button').trigger('click')
    await flushPromises()

    expect(
      wrapper
        .findAll('.agent-conversations__item-name')
        .map((item) => item.text())
    ).toEqual(['Order status'])
    expect(messages(wrapper)).toEqual(['ViewerWhere is my order?'])
  })

  test('offers to load the messages again when that failed', async () => {
    mockConfiguration(testApp, templateConfiguration())
    mockConversations(
      testApp,
      conversationsPage([
        { ...conversation('first', 'Order status'), shared: true },
      ])
    )
    mockMessages(
      testApp,
      'first',
      [500, {}],
      page([message('user', 'Where is my order?', { id: 1 })])
    )
    const wrapper = await mountPreview()

    // Not shown as if the example were an empty chat.
    expect(wrapper.find('.agent-chat__intro').exists()).toBe(false)
    expect(wrapper.get('.agent-chat .alert').text()).toContain(
      'agent.messagesLoadError'
    )
    await wrapper.get('.agent-chat .alert .button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.agent-chat .alert').exists()).toBe(false)
    expect(messages(wrapper)).toEqual(['ViewerWhere is my order?'])
  })

  test('offers to load the configuration again when that failed', async () => {
    mockConfiguration(testApp, [500, {}], templateConfiguration())
    mockConversations(testApp, conversationsPage([]))
    const wrapper = await testApp.mount(AgentTemplate, {
      props: { pageValue: { agent: { ...agentData, integrations: [] } } },
    })
    await flushPromises()

    await wrapper.get('.agent-configuration .alert .button').trigger('click')
    await flushPromises()

    expect(
      wrapper.findAll('.agent-configuration .menu-list__item-button')
    ).toHaveLength(7)
  })
})
