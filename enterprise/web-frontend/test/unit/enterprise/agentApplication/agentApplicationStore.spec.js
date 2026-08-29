import { expect } from 'vitest'
import MockAdapter from 'axios-mock-adapter'

describe('agentApplication store', () => {
  let store = null
  let mock = null

  beforeEach(() => {
    const { $store, $client } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
  })

  afterEach(() => {
    mock.restore()
  })

  test('update sends a plain partial payload', async () => {
    mock.onGet('agent_application/42/agent/').replyOnce(200, {
      id: 6,
      application_id: 42,
      name: 'Agent',
      instructions: 'Old',
      ai_generative_ai_type: 'openai',
      ai_generative_ai_model: 'gpt-4.1-nano',
      ai_temperature: null,
    })
    await store.dispatch('agentApplication/fetch', { applicationId: 42 })

    let requestBody = null
    mock.onPatch('agent_application/agents/6/').replyOnce((config) => {
      requestBody = JSON.parse(config.data)
      return [200, { ...requestBody, id: 6 }]
    })

    await store.dispatch('agentApplication/update', {
      agentId: 6,
      values: { name: 'Agent', instructions: 'New' },
    })

    expect(requestBody).toStrictEqual({ name: 'Agent', instructions: 'New' })
    expect(store.getters['agentApplication/getAgent'].instructions).toBe('New')
    // Fields not part of the partial payload must be preserved locally.
    expect(
      store.getters['agentApplication/getAgent'].ai_generative_ai_type
    ).toBe('openai')
  })

  describe('triggers', () => {
    test('fetchTriggers stores the configured triggers', async () => {
      mock.onGet('agent_application/42/triggers/').replyOnce(200, [
        {
          id: 1,
          enabled: true,
          service_type: 'periodic',
          service: { interval: 'HOUR', minute: 0 },
        },
        {
          id: 2,
          enabled: false,
          service_type: 'local_baserow_rows_created',
          service: { table_id: 5 },
        },
      ])

      await store.dispatch('agentApplication/fetchTriggers', {
        applicationId: 42,
      })

      const triggers = store.getters['agentApplication/getTriggers']
      expect(triggers.length).toBe(2)
      expect(triggers[0]).toStrictEqual({
        id: 1,
        enabled: true,
        service_type: 'periodic',
        service: { interval: 'HOUR', minute: 0 },
      })
    })

    test('createTrigger appends the created trigger', async () => {
      mock.onPost('agent_application/42/triggers/').replyOnce(200, {
        id: 3,
        enabled: true,
        service_type: 'local_baserow_rows_created',
        service: { table_id: null },
      })

      await store.dispatch('agentApplication/createTrigger', {
        applicationId: 42,
        values: { service_type: 'local_baserow_rows_created' },
      })

      const triggers = store.getters['agentApplication/getTriggers']
      expect(triggers.find((trigger) => trigger.id === 3).service_type).toBe(
        'local_baserow_rows_created'
      )
    })

    test('updateTrigger merges the response into the matching trigger', async () => {
      mock.onGet('agent_application/42/triggers/').replyOnce(200, [
        {
          id: 3,
          enabled: true,
          service_type: 'local_baserow_rows_created',
          service: { table_id: null },
        },
      ])
      await store.dispatch('agentApplication/fetchTriggers', {
        applicationId: 42,
      })

      mock.onPatch('agent_application/triggers/3/').replyOnce(200, {
        id: 3,
        enabled: false,
        service_type: 'local_baserow_rows_created',
        service: { table_id: 6 },
      })

      await store.dispatch('agentApplication/updateTrigger', {
        triggerId: 3,
        values: { enabled: false },
      })

      const trigger = store.getters['agentApplication/getTriggers'].find(
        (t) => t.id === 3
      )
      expect(trigger.enabled).toBe(false)
      expect(trigger.service.table_id).toBe(6)
    })

    test('deleteTrigger removes the trigger', async () => {
      mock.onGet('agent_application/42/triggers/').replyOnce(200, [
        {
          id: 3,
          enabled: true,
          service_type: 'periodic',
          service: { interval: 'HOUR', minute: 0 },
        },
      ])
      await store.dispatch('agentApplication/fetchTriggers', {
        applicationId: 42,
      })

      mock.onDelete('agent_application/triggers/3/').replyOnce(204)

      await store.dispatch('agentApplication/deleteTrigger', { triggerId: 3 })

      expect(
        store.getters['agentApplication/getTriggers'].find(
          (trigger) => trigger.id === 3
        )
      ).toBeUndefined()
    })
  })

  describe('tools', () => {
    test('fetchTools stores the tools', async () => {
      mock.onGet('agent_application/42/tools/').replyOnce(200, [
        { id: 1, type: 'workspace', name: '', config: {} },
        {
          id: 2,
          type: 'service',
          name: 'create_task',
          config: { description: '', inputs: [] },
          service_type: 'local_baserow_create_row',
          service: { table_id: 5 },
        },
      ])

      await store.dispatch('agentApplication/fetchTools', {
        applicationId: 42,
      })

      expect(store.getters['agentApplication/getTools'].length).toBe(2)
    })

    test('createTool appends the created tool', async () => {
      mock
        .onPost('agent_application/42/tools/')
        .replyOnce(200, { id: 3, type: 'web_search', name: '', config: {} })

      await store.dispatch('agentApplication/createTool', {
        applicationId: 42,
        values: { type: 'web_search' },
      })

      const tools = store.getters['agentApplication/getTools']
      expect(tools.find((tool) => tool.id === 3).type).toBe('web_search')
    })

    test('updateTool merges the response into the matching tool', async () => {
      mock.onPatch('agent_application/tools/2/').replyOnce(200, {
        id: 2,
        type: 'service',
        name: 'create_task_renamed',
        config: { description: 'updated', inputs: [] },
        service_type: 'local_baserow_create_row',
        service: { table_id: 6 },
      })

      await store.dispatch('agentApplication/updateTool', {
        toolId: 2,
        values: { name: 'create_task_renamed' },
      })

      const tool = store.getters['agentApplication/getTools'].find(
        (t) => t.id === 2
      )
      expect(tool.name).toBe('create_task_renamed')
      expect(tool.service.table_id).toBe(6)
    })

    test('deleteTool removes the tool', async () => {
      mock.onDelete('agent_application/tools/3/').replyOnce(204)

      await store.dispatch('agentApplication/deleteTool', { toolId: 3 })

      expect(
        store.getters['agentApplication/getTools'].find((tool) => tool.id === 3)
      ).toBeUndefined()
    })
  })

  describe('channels', () => {
    const slackChannel = (values = {}) => ({
      id: 1,
      type: 'slack',
      name: 'Support Slack',
      enabled: true,
      config: { bot_token_set: true, signing_secret_set: true },
      events_url: 'http://backend/api/agent_application/channels/uid/events/',
      ...values,
    })

    test('fetchChannels stores the channels', async () => {
      mock
        .onGet('agent_application/42/channels/')
        .replyOnce(200, [slackChannel()])

      await store.dispatch('agentApplication/fetchChannels', {
        applicationId: 42,
      })

      const channels = store.getters['agentApplication/getChannels']
      expect(channels.length).toBe(1)
      expect(channels[0]).toStrictEqual(slackChannel())
    })

    test('createChannel appends the created channel', async () => {
      let requestBody = null
      mock.onPost('agent_application/42/channels/').replyOnce((config) => {
        requestBody = JSON.parse(config.data)
        return [200, slackChannel({ id: 2 })]
      })

      await store.dispatch('agentApplication/createChannel', {
        applicationId: 42,
        values: {
          type: 'slack',
          name: 'Support Slack',
          config: { bot_token: 'xoxb-secret', signing_secret: 'shh' },
        },
      })

      expect(requestBody).toStrictEqual({
        type: 'slack',
        name: 'Support Slack',
        config: { bot_token: 'xoxb-secret', signing_secret: 'shh' },
      })
      const channel = store.getters['agentApplication/getChannels'].find(
        (c) => c.id === 2
      )
      // The response only contains the masked config.
      expect(channel.config).toStrictEqual({
        bot_token_set: true,
        signing_secret_set: true,
      })
    })

    test('updateChannel applies non-config values optimistically', async () => {
      mock
        .onGet('agent_application/42/channels/')
        .replyOnce(200, [slackChannel()])
      await store.dispatch('agentApplication/fetchChannels', {
        applicationId: 42,
      })

      let resolveResponse = null
      mock.onPatch('agent_application/channels/1/').replyOnce(
        () =>
          new Promise((resolve) => {
            resolveResponse = () =>
              resolve([200, slackChannel({ enabled: false })])
          })
      )

      const promise = store.dispatch('agentApplication/updateChannel', {
        channelId: 1,
        values: { enabled: false },
      })

      // The switch state must change before the server confirms.
      expect(store.getters['agentApplication/getChannels'][0].enabled).toBe(
        false
      )
      while (resolveResponse === null) {
        await new Promise((resolve) => setTimeout(resolve))
      }
      resolveResponse()
      await promise
      expect(store.getters['agentApplication/getChannels'][0].enabled).toBe(
        false
      )
    })

    test('updateChannel reverts the optimistic value when the request fails', async () => {
      mock
        .onGet('agent_application/42/channels/')
        .replyOnce(200, [slackChannel()])
      await store.dispatch('agentApplication/fetchChannels', {
        applicationId: 42,
      })

      mock.onPatch('agent_application/channels/1/').replyOnce(400)

      await expect(
        store.dispatch('agentApplication/updateChannel', {
          channelId: 1,
          values: { enabled: false },
        })
      ).rejects.toThrow()

      expect(store.getters['agentApplication/getChannels'][0].enabled).toBe(
        true
      )
    })

    test('updateChannel never stores the plain secrets from a config patch', async () => {
      mock.onGet('agent_application/42/channels/').replyOnce(200, [
        slackChannel({
          config: { bot_token_set: false, signing_secret_set: true },
        }),
      ])
      await store.dispatch('agentApplication/fetchChannels', {
        applicationId: 42,
      })

      let requestBody = null
      mock.onPatch('agent_application/channels/1/').replyOnce((config) => {
        requestBody = JSON.parse(config.data)
        return [200, slackChannel()]
      })

      await store.dispatch('agentApplication/updateChannel', {
        channelId: 1,
        values: { config: { bot_token: 'xoxb-secret' } },
      })

      expect(requestBody).toStrictEqual({
        config: { bot_token: 'xoxb-secret' },
      })
      // The store only ever holds the masked config from the response.
      expect(
        store.getters['agentApplication/getChannels'][0].config
      ).toStrictEqual({ bot_token_set: true, signing_secret_set: true })
    })

    test('deleteChannel removes the channel', async () => {
      mock
        .onGet('agent_application/42/channels/')
        .replyOnce(200, [slackChannel()])
      await store.dispatch('agentApplication/fetchChannels', {
        applicationId: 42,
      })

      mock.onDelete('agent_application/channels/1/').replyOnce(204)

      await store.dispatch('agentApplication/deleteChannel', { channelId: 1 })

      expect(store.getters['agentApplication/getChannels'].length).toBe(0)
    })
  })
})
