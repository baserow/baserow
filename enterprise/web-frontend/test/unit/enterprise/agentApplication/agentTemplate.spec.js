import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import MockAdapter from 'axios-mock-adapter'

import AgentTemplate from '@baserow_enterprise/components/agentApplication/AgentTemplate'
import { AgentApplicationType } from '@baserow_enterprise/agentApplication/applicationTypes'

const application = {
  id: 3,
  name: 'Docs agent',
  workspace: { id: 1, name: 'Template workspace' },
  pending_approvals_count: 0,
}

describe('AgentTemplate', () => {
  let mock = null
  let store = null

  beforeEach(() => {
    const { $client, $store } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
    mock.onGet('agent_application/3/agent/').reply(200, {
      id: 9,
      application_id: 3,
      name: 'Docs agent',
      description: 'Answers questions.',
      instructions: '## Goal\nHelp with the docs.',
      skills: [],
    })
    mock
      .onGet('agent_application/3/triggers/')
      .reply(200, [
        { id: 1, service_type: 'periodic', enabled: true, service: {} },
      ])
    mock.onGet('agent_application/3/tools/').reply(200, [
      { id: 1, type: 'workspace', name: '', config: {}, service_type: null },
      {
        id: 2,
        type: 'service',
        name: 'Send email',
        config: {},
        service_type: 'smtp_email',
        service: {},
      },
    ])
    mock.onGet('agent_application/3/channels/').reply(403)
    mock.onGet('agent_application/3/workspace_tools/').reply(200, [])
    mock.onGet('agent_application/3/chats/').reply(200, {
      count: 2,
      next: null,
      results: [
        {
          id: 21,
          uuid: 'u-21',
          title: 'How it works',
          pinned: true,
          status: 'idle',
          source: 'manual',
        },
        {
          id: 22,
          uuid: 'u-22',
          title: 'Weekly digest',
          pinned: true,
          status: 'idle',
          source: 'manual',
        },
      ],
    })
    mock.onGet('agent_application/3/chats/u-21/messages/').reply(200, {
      chat: { id: 21, uuid: 'u-21', status: 'idle', source: 'manual' },
      tool_approvals: [],
      messages: [
        { id: 1, chat_id: 21, role: 'human', content: 'Hi there' },
        { id: 2, chat_id: 21, role: 'ai', content: 'Hello **you**' },
      ],
    })
  })

  afterEach(() => {
    mock.restore()
  })

  test('the application type offers a template preview', () => {
    const type = new AgentApplicationType({ app: {} })
    expect(type.getTemplatePage(application)).toEqual({ application })
    expect(type.getTemplatesPageComponent()).toBe(AgentTemplate)
    expect(type.getTemplateSidebarComponent()).toBeTruthy()
  })

  test('shows the example conversations and the configuration read-only', async () => {
    const wrapper = await mountSuspended(AgentTemplate, {
      props: { pageValue: { application } },
    })
    await flushPromises()

    // The real stores are left untouched; the preview has its own copies.
    expect(store.getters['agentApplication/getAgent']).toBeNull()
    expect(store.getters['template/agentApplication/getAgent'].id).toBe(9)

    const text = wrapper.text()
    expect(text).toContain('How it works')
    expect(text).toContain('Weekly digest')
    // The first conversation opens by itself.
    expect(text).toContain('Hi there')
    expect(text).toContain('Hello')
    expect(store.getters['template/agentChat/getCurrentChatUuid']).toBe('u-21')

    // Nothing can be sent, started or changed on a template, whatever the
    // test permission helper says.
    expect(wrapper.find('.agent-chat__composer').exists()).toBe(false)
    expect(text).not.toContain('agentConversationList.newConversation')
    expect(text).not.toContain('agentHeader.runOnce')
    expect(wrapper.find('.agent-page__header-status').exists()).toBe(false)
    expect(wrapper.find('.agent-page__header-approvals').exists()).toBe(false)

    // The real configuration panel is open with its sections.
    const rows = wrapper.findAll('.agent-configuration-row')
    expect(rows.length).toBe(7)
    expect(text).toContain('agentConfiguration.whenItRuns')
    expect(text).toContain('Send email')
  })
})
