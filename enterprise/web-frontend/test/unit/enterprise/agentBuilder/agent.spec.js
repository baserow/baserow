import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentService from '@baserow_enterprise/agentBuilder/services/agent'
import { registerRealtimeEvents } from '@baserow_enterprise/realtime'
import { generateHash } from '@baserow/modules/core/utils/hashing'

vi.mock('@baserow_enterprise/agentBuilder/services/agent', () => ({
  default: vi.fn(),
}))

describe('Agent Builder agents', () => {
  let testApp, store, agentBuilder, service
  const first = { id: 11, agent_builder_id: 10, name: 'First', order: 1 }
  const second = { id: 12, agent_builder_id: 10, name: 'Second', order: 2 }

  beforeEach(async () => {
    vi.clearAllMocks()
    testApp = new TestApp()
    store = testApp.store
    service = {
      fetchAll: vi.fn().mockResolvedValue({ data: [first, second] }),
      create: vi.fn().mockResolvedValue({ data: first }),
      read: vi.fn().mockResolvedValue({ data: first }),
      update: vi
        .fn()
        .mockResolvedValue({ data: { ...first, name: 'Renamed' } }),
      delete: vi.fn().mockResolvedValue({}),
    }
    AgentService.mockReturnValue(service)
    await store.dispatch('application/forceCreate', {
      id: 10,
      type: 'agent_builder',
      name: 'Agents',
      workspace: { id: 1 },
    })
    agentBuilder = store.getters['application/get'](10)
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  test('fetch uses the separate permission-filtered child endpoint', async () => {
    service.fetchAll.mockResolvedValue({ data: [second] })
    await store.dispatch('agentBuilderAgent/fetch', agentBuilder)
    expect(agentBuilder.agents).toEqual([second])
    expect(service.fetchAll).toHaveBeenCalledWith(agentBuilder.id)
  })

  test('create plus realtime delivery adds an agent once', async () => {
    const events = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => (events[name] = handler),
    })
    await store.dispatch('agentBuilderAgent/create', {
      agentBuilder,
      name: first.name,
    })
    events.agent_builder_agent_created({ store }, { agent: first })
    expect(agentBuilder.agents).toEqual([first])
    expect(service.create).toHaveBeenCalledWith(10, first.name)
  })

  test('renames a specific agent while preserving its sibling', async () => {
    await store.dispatch('agentBuilderAgent/fetch', agentBuilder)
    await store.dispatch('agentBuilderAgent/update', {
      agentBuilder,
      agent: first,
      values: { name: 'Renamed' },
    })
    expect(agentBuilder.agents.map(({ name }) => name)).toEqual([
      'Renamed',
      'Second',
    ])
    expect(service.update).toHaveBeenCalledWith(first.id, { name: 'Renamed' })
  })

  test('realtime ordering uses hashed IDs without adding inaccessible agents', async () => {
    const events = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => (events[name] = handler),
    })
    await store.dispatch('agentBuilderAgent/fetch', agentBuilder)
    events.agent_builder_agents_reordered(
      { store },
      {
        agent_builder_id: generateHash(agentBuilder.id),
        order: [
          generateHash(second.id),
          generateHash(99),
          generateHash(first.id),
        ],
      }
    )
    expect(
      store.getters['agentBuilderAgent/getOrdered'](agentBuilder).map(
        ({ id }) => id
      )
    ).toEqual([second.id, first.id])
    expect(agentBuilder.agents).toHaveLength(2)
  })

  test('rejects an agent from a different application', async () => {
    service.read.mockResolvedValue({ data: { ...first, agent_builder_id: 99 } })
    await expect(
      store.dispatch('agentBuilderAgent/read', {
        agentBuilder,
        agentId: first.id,
      })
    ).rejects.toThrow('Agent not found')
    expect(agentBuilder.agents).toEqual([])
  })

  test('deleting a sibling preserves the selected agent', async () => {
    await store.dispatch('agentBuilderAgent/fetch', agentBuilder)
    await store.dispatch('agentBuilderAgent/select', second.id)
    await store.dispatch('agentBuilderAgent/delete', {
      agentBuilder,
      agent: first,
    })
    expect(agentBuilder.agents).toEqual([second])
    expect(store.getters['agentBuilderAgent/getSelectedId']).toBe(second.id)
  })

  test('a realtime deletion of the selected agent returns to the builder', async () => {
    const push = vi
      .spyOn(testApp.nuxtApp.$router, 'push')
      .mockResolvedValue(undefined)
    await store.dispatch('agentBuilderAgent/fetch', agentBuilder)
    await store.dispatch('agentBuilderAgent/select', first.id)
    await store.dispatch('agentBuilderAgent/forceDelete', {
      agentBuilder,
      agentId: first.id,
    })
    expect(store.getters['agentBuilderAgent/getSelectedId']).toBeNull()
    expect(agentBuilder.agents).toEqual([second])
    expect(push).toHaveBeenCalledWith({
      name: 'agent-builder',
      params: { agentBuilderId: agentBuilder.id },
    })
  })

  test.each([true, false])(
    'a permission change removes inaccessible agents when list access is %s',
    async (canList) => {
      const events = {}
      registerRealtimeEvents({
        registerEvent: (name, handler) => (events[name] = handler),
      })
      const push = vi.fn().mockResolvedValue(undefined)
      const app = { $hasPermission: () => canList, $router: { push } }
      await store.dispatch('workspace/forceCreate', {
        id: 1,
        name: 'Workspace',
      })
      testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
      await store.dispatch('application/select', agentBuilder)
      await store.dispatch('agentBuilderAgent/fetch', agentBuilder)
      await store.dispatch('agentBuilderAgent/select', first.id)
      await store.dispatch('application/forceCreate', {
        id: 20,
        type: 'agent_builder',
        name: 'Other builder',
        workspace: { id: 1 },
      })
      const otherBuilder = store.getters['application/get'](20)
      store.commit('agentBuilderAgent/SET_AGENTS', {
        agentBuilder: otherBuilder,
        agents: [
          { id: 21, agent_builder_id: 20, name: 'Other agent', order: 1 },
        ],
      })
      service.fetchAll.mockResolvedValue({ data: [second] })

      await events.permissions_updated({ store, app }, { workspace_id: 1 })

      expect(agentBuilder.agents).toEqual(canList ? [second] : [])
      expect(otherBuilder.agents).toEqual([])
      expect(store.getters['agentBuilderAgent/getSelectedId']).toBeNull()
      expect(push).toHaveBeenCalledWith(
        canList
          ? {
              name: 'agent-builder',
              params: { agentBuilderId: agentBuilder.id },
            }
          : { name: 'workspace', params: { workspaceId: 1 } }
      )
    }
  )
})
