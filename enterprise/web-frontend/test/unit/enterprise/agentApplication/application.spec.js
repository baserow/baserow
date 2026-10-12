import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Agent shared application lifecycle', () => {
  let testApp, store
  const workspace = { id: 1, name: 'Workspace' }
  const agent = {
    id: 10,
    type: 'agent',
    name: 'Support agent',
    workspace: { id: 1 },
    order: 1,
  }

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    await store.dispatch('workspace/forceCreate', workspace)
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  async function emitApplicationEvent(name, payload) {
    for (const callback of testApp.nuxtApp.$realtime.events[name]) {
      await callback({ store, app: testApp.nuxtApp }, payload)
    }
    await flushPromises()
  }

  test('creates the agent directly with the application endpoint', async () => {
    testApp.mock.onPost('/applications/workspace/1/').reply(200, agent)
    const created = await store.dispatch('application/create', {
      type: 'agent',
      workspace,
      values: { name: agent.name },
    })
    expect(created.id).toBe(agent.id)
    expect(created.type).toBe('agent')
    expect(created).not.toHaveProperty('agents')
    expect(testApp.mock.history.post).toHaveLength(1)
    expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
      type: 'agent',
      name: agent.name,
      init_with_data: true,
    })
  })

  test('applies shared realtime creation and renaming without child data', async () => {
    await emitApplicationEvent('application_created', { application: agent })
    await emitApplicationEvent('application_created', { application: agent })
    expect(store.getters['application/getAll']).toHaveLength(1)
    await emitApplicationEvent('application_updated', {
      application_id: agent.id,
      application: { ...agent, name: 'Renamed agent' },
    })
    const updated = store.getters['application/get'](agent.id)
    expect(updated.name).toBe('Renamed agent')
    expect(updated).not.toHaveProperty('agents')
  })

  test('a shared realtime deletion returns the selected agent to its workspace', async () => {
    const push = vi.spyOn(testApp.nuxtApp.$router, 'push').mockResolvedValue()
    await store.dispatch('application/forceCreate', agent)
    await store.dispatch('application/selectById', agent.id)
    await emitApplicationEvent('application_deleted', {
      application_id: agent.id,
    })
    expect(store.getters['application/get'](agent.id)).toBeUndefined()
    expect(push).toHaveBeenCalledWith({
      name: 'workspace',
      params: { workspaceId: workspace.id },
    })
  })
})
