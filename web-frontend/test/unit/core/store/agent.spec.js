import { beforeEach, describe, expect, test, vi } from 'vitest'

import {
  actions,
  mutations,
  state as makeState,
} from '@baserow/modules/core/store/agent'
import AgentService from '@baserow/modules/core/services/agent'

vi.mock('@baserow/modules/core/services/agent', () => ({
  default: vi.fn(),
}))

describe('Agent store', () => {
  let service

  beforeEach(() => {
    service = {
      fetch: vi.fn().mockResolvedValue({
        data: {
          count: 1,
          results: [{ id: 1, workspace_id: 42, name: 'Writer' }],
        },
      }),
      create: vi.fn().mockResolvedValue({
        data: { id: 2, workspace_id: 42, name: 'Researcher' },
      }),
      update: vi.fn().mockResolvedValue({
        data: { id: 1, workspace_id: 42, name: 'Editor' },
      }),
      delete: vi.fn().mockResolvedValue({}),
    }
    AgentService.mockReturnValue(service)
  })

  test('fetching a page merges its agents into the store', async () => {
    const commit = vi.fn()
    const args = ['/agents/workspace/42/', 1, false, [], {}, {}]

    const response = await actions.fetchPage.call(
      { $client: {} },
      { commit },
      { args }
    )

    expect(service.fetch).toHaveBeenCalledWith(...args)
    expect(commit).toHaveBeenCalledWith('MERGE_ITEMS', response.data.results)
  })

  test('real-time mutations update agents and advance the workspace revision', () => {
    const state = makeState()
    const agent = { id: 1, workspace_id: 42, name: 'Writer' }

    mutations.UPSERT_ITEM(state, agent)
    mutations.UPSERT_ITEM(state, { ...agent, name: 'Editor' })

    expect(state.items).toEqual([{ ...agent, name: 'Editor' }])
    expect(state.revisions[42]).toBe(2)

    mutations.DELETE_ITEM(state, { workspaceId: 42, agentId: 1 })

    expect(state.items).toEqual([])
    expect(state.revisions[42]).toBe(3)
  })

  test('CRUD actions update the store through their force actions', async () => {
    const dispatch = vi.fn((type, payload) => payload)

    await actions.create.call(
      { $client: {} },
      { dispatch },
      { workspaceId: 42, values: { name: 'Researcher' } }
    )
    await actions.update.call(
      { $client: {} },
      { dispatch },
      { agentId: 1, values: { name: 'Editor' } }
    )
    await actions.delete.call(
      { $client: {} },
      { dispatch },
      { id: 1, workspace_id: 42 }
    )

    expect(dispatch).toHaveBeenCalledWith('forceCreate', {
      id: 2,
      workspace_id: 42,
      name: 'Researcher',
    })
    expect(dispatch).toHaveBeenCalledWith('forceUpdate', {
      id: 1,
      workspace_id: 42,
      name: 'Editor',
    })
    expect(dispatch).toHaveBeenCalledWith('forceDelete', {
      workspaceId: 42,
      agentId: 1,
    })
  })
})
