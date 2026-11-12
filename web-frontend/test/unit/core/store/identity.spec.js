import { beforeEach, describe, expect, test, vi } from 'vitest'

import {
  actions,
  mutations,
  state as makeState,
} from '@baserow/modules/core/store/identity'
import IdentityService from '@baserow/modules/core/services/identity'

vi.mock('@baserow/modules/core/services/identity', () => ({
  default: vi.fn(),
}))

describe('Identity store', () => {
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
    IdentityService.mockReturnValue(service)
  })

  test('fetching a page merges its identities into the store', async () => {
    const commit = vi.fn()
    const state = makeState()
    const args = ['/identities/workspace/42/', 1, false, [], {}, {}]

    const response = await actions.fetchPage.call(
      { $client: {} },
      { commit, state },
      { args, workspaceId: 42 }
    )

    expect(service.fetch).toHaveBeenCalledWith(...args)
    expect(commit).toHaveBeenCalledWith('MERGE_ITEMS', response.data.results)
  })

  test('a stale page cannot overwrite a newer real-time update', async () => {
    const state = makeState()
    const commit = (type, payload) => mutations[type](state, payload)
    let resolveFetch
    service.fetch.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveFetch = resolve
      })
    )

    const fetch = actions.fetchPage.call(
      { $client: {} },
      { commit, state },
      { args: [], workspaceId: 42 }
    )
    mutations.UPSERT_ITEM(state, {
      id: 1,
      workspace_id: 42,
      name: 'Real-time identity',
    })
    resolveFetch({
      data: {
        count: 1,
        results: [{ id: 1, workspace_id: 42, name: 'Stale identity' }],
      },
    })
    await fetch

    expect(state.items).toEqual([
      { id: 1, workspace_id: 42, name: 'Real-time identity' },
    ])
  })

  test('real-time mutations update identities and advance the workspace revision', () => {
    const state = makeState()
    const identity = { id: 1, workspace_id: 42, name: 'Writer' }

    mutations.UPSERT_ITEM(state, identity)
    mutations.UPSERT_ITEM(state, { ...identity, name: 'Editor' })

    expect(state.items).toEqual([{ ...identity, name: 'Editor' }])
    expect(state.revisions[42]).toBe(2)

    mutations.DELETE_ITEM(state, { workspaceId: 42, identityId: 1 })

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
      { identityId: 1, values: { name: 'Editor' } }
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
      identityId: 1,
    })
  })

  test('force actions keep the workspace members count in sync', () => {
    const state = makeState()
    const commit = (type, payload) => mutations[type](state, payload)
    const dispatch = vi.fn()
    const identity = { id: 1, workspace_id: 42, name: 'Writer' }

    actions.forceCreate({ commit, state, dispatch }, identity)
    actions.forceCreate({ commit, state, dispatch }, identity)
    actions.forceDelete(
      { commit, state, dispatch },
      { workspaceId: 42, identityId: 1 }
    )

    expect(dispatch).toHaveBeenNthCalledWith(
      1,
      'workspace/updateIdentitiesCount',
      { workspaceId: 42, delta: 1 },
      { root: true }
    )
    expect(dispatch).toHaveBeenNthCalledWith(
      2,
      'workspace/updateIdentitiesCount',
      { workspaceId: 42, delta: -1 },
      { root: true }
    )
    expect(dispatch).toHaveBeenCalledTimes(2)
  })
})
