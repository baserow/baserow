import { expect } from 'vitest'

import { registerRealtimeEvents } from '@baserow_enterprise/realtime'

describe('agent realtime events', () => {
  let store = null
  let events = null

  beforeEach(async () => {
    const { $store } = useNuxtApp()
    store = $store
    events = {}
    registerRealtimeEvents({
      registerEvent(name, handler) {
        events[name] = handler
      },
    })
    await store.dispatch('agentApplication/forceUpdate', {
      values: {
        id: 7,
        application_id: 42,
        name: 'Agent',
        instructions: 'Old',
        skills: [
          { id: 1, skill_id: 10, name: 'Tone', mode: 'always' },
          { id: 2, skill_id: 11, name: 'Rules', mode: 'on_demand' },
        ],
      },
    })
  })

  test('definition updates are applied for the open agent only', async () => {
    await events.agent_definition_updated(
      { store },
      { agent: { id: 99, application_id: 1, instructions: 'Other agent' } }
    )
    expect(store.getters['agentApplication/getAgent'].instructions).toBe('Old')

    await events.agent_definition_updated(
      { store },
      { agent: { id: 7, application_id: 42, instructions: 'New' } }
    )
    expect(store.getters['agentApplication/getAgent'].instructions).toBe('New')
  })

  test('conversations of another agent are ignored', async () => {
    await events.agent_chat_updated(
      { store },
      {
        chat: {
          id: 500,
          uuid: 'other',
          agent_id: 99,
          title: 'Other',
          status: 'idle',
          pinned: false,
          source: 'manual',
        },
      }
    )
    expect(
      store.getters['agentHistory/getChats'].some((chat) => chat.id === 500)
    ).toBe(false)

    await events.agent_chat_updated(
      { store },
      {
        chat: {
          id: 501,
          uuid: 'mine',
          agent_id: 7,
          title: 'Mine',
          status: 'idle',
          pinned: false,
          source: 'manual',
        },
      }
    )
    expect(
      store.getters['agentHistory/getChats'].some((chat) => chat.id === 501)
    ).toBe(true)
  })

  test('a deleted workspace skill disappears from the agent', async () => {
    await events.workspace_skill_deleted(
      { store },
      { workspace_id: 1, skill_id: 10 }
    )
    expect(
      store.getters['agentApplication/getAgent'].skills.map((s) => s.skill_id)
    ).toEqual([11])

    // Unknown skills leave the agent untouched.
    await events.workspace_skill_deleted(
      { store },
      { workspace_id: 1, skill_id: 999 }
    )
    expect(store.getters['agentApplication/getAgent'].skills).toHaveLength(1)
  })

  test('configuration events apply the broadcast object to the open agent', async () => {
    await store.dispatch('agentApplication/forceCreateTrigger', {
      trigger: { id: 1, service_type: 'periodic', enabled: true, service: {} },
    })
    await store.dispatch('agentApplication/forceCreateTool', {
      tool: { id: 2, type: 'service', name: 'Mail', service: {} },
    })
    await store.dispatch('agentApplication/forceCreateChannel', {
      channel: { id: 3, type: 'web', name: 'Web', enabled: true },
    })

    // Another application's change leaves this agent alone.
    await events.agent_trigger_deleted(
      { store },
      { application_id: 1, trigger_id: 1 }
    )
    expect(store.getters['agentApplication/getTriggers']).toHaveLength(1)

    await events.agent_trigger_updated(
      { store },
      {
        application_id: 42,
        trigger: {
          id: 1,
          service_type: 'periodic',
          enabled: false,
          service: { interval: 'DAY' },
        },
      }
    )
    expect(store.getters['agentApplication/getTriggers'][0]).toMatchObject({
      enabled: false,
      service: { interval: 'DAY' },
    })

    await events.agent_trigger_created(
      { store },
      { application_id: 42, trigger: { id: 9, service_type: 'http_trigger' } }
    )
    // A restore of a trigger the client still holds is not duplicated.
    await events.agent_trigger_created(
      { store },
      { application_id: 42, trigger: { id: 9, service_type: 'http_trigger' } }
    )
    expect(
      store.getters['agentApplication/getTriggers'].map((t) => t.id)
    ).toEqual([1, 9])

    await events.agent_trigger_deleted(
      { store },
      { application_id: 42, trigger_id: 1 }
    )
    expect(
      store.getters['agentApplication/getTriggers'].map((t) => t.id)
    ).toEqual([9])

    await events.agent_tool_updated(
      { store },
      { application_id: 42, tool: { id: 2, type: 'service', name: 'Renamed' } }
    )
    expect(store.getters['agentApplication/getTools'][0].name).toBe('Renamed')
    await events.agent_tool_deleted(
      { store },
      { application_id: 42, tool_id: 2 }
    )
    expect(store.getters['agentApplication/getTools']).toHaveLength(0)

    await events.agent_chat_channel_updated(
      { store },
      {
        application_id: 42,
        channel: { id: 3, type: 'web', name: 'Web', enabled: false },
      }
    )
    expect(store.getters['agentApplication/getChannels'][0].enabled).toBe(false)
    await events.agent_chat_channel_created(
      { store },
      { application_id: 42, channel: { id: 4, type: 'slack', name: 'Slack' } }
    )
    await events.agent_chat_channel_deleted(
      { store },
      { application_id: 42, channel_id: 3 }
    )
    expect(
      store.getters['agentApplication/getChannels'].map((c) => c.id)
    ).toEqual([4])
  })
})
