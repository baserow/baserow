import { beforeEach, describe, expect, test, vi } from 'vitest'

import {
  actions,
  mutations,
  state as makeState,
} from '@baserow/modules/core/store/aiProvider'
import aiProviderService from '@baserow/modules/core/services/aiProvider'

vi.mock('@baserow/modules/core/services/aiProvider', () => ({
  default: vi.fn(),
}))

describe('AI provider store', () => {
  let service

  beforeEach(() => {
    vi.clearAllMocks()
    service = {
      fetchAll: vi.fn().mockResolvedValue({ data: [{ id: 1 }] }),
      fetchTypes: vi.fn().mockResolvedValue({ data: [{ type: 'openai' }] }),
      discoverModels: vi.fn().mockResolvedValue({
        data: { models: ['gpt-5.6'], supported: true },
      }),
      update: vi.fn().mockResolvedValue({ data: { id: 1, is_active: false } }),
      updateModel: vi.fn().mockResolvedValue({ data: { id: 2 } }),
      testModels: vi.fn().mockResolvedValue({
        data: {
          results: [
            {
              model_id: 2,
              status: 'success',
              error: '',
              tested_at: '2026-07-21T12:00:00Z',
            },
          ],
        },
      }),
    }
    aiProviderService.mockReturnValue(service)
  })

  test('fetchInitial loads providers and supported types', async () => {
    const committed = []
    await actions.fetchInitial.call(
      { $client: {} },
      { commit: (type, payload) => committed.push([type, payload]) }
    )

    expect(service.fetchAll).toHaveBeenCalledOnce()
    expect(service.fetchTypes).toHaveBeenCalledOnce()
    expect(committed).toContainEqual(['SET_PROVIDERS', [{ id: 1 }]])
    expect(committed).toContainEqual([
      'SET_PROVIDER_TYPES',
      [{ type: 'openai' }],
    ])
    expect(committed.at(-1)).toEqual(['SET_LOADING', false])
  })

  test('refresh replaces provider state without reloading provider types', async () => {
    const commit = vi.fn()
    const storeState = makeState()

    const providers = await actions.refresh.call(
      { $client: {} },
      { commit, state: storeState }
    )

    expect(aiProviderService).toHaveBeenCalledWith({}, null)
    expect(service.fetchAll).toHaveBeenCalledOnce()
    expect(service.fetchTypes).not.toHaveBeenCalled()
    expect(commit).toHaveBeenCalledWith('SET_PROVIDERS', [{ id: 1 }])
    expect(providers).toEqual([{ id: 1 }])
  })

  test('workspace actions scope all requests to the workspace', async () => {
    const committed = []
    await actions.fetchInitial.call(
      { $client: {} },
      { commit: (type, payload) => committed.push([type, payload]) },
      { workspaceId: 42 }
    )

    expect(aiProviderService).toHaveBeenCalledWith({}, 42)
    expect(committed).toContainEqual(['SET_WORKSPACE_ID', 42])

    const values = { is_active: false }
    await actions.update.call(
      { $client: {} },
      { commit: vi.fn() },
      { providerId: 1, values, workspaceId: 42 }
    )

    expect(aiProviderService).toHaveBeenLastCalledWith({}, 42)
    expect(service.update).toHaveBeenCalledWith(1, values)
  })

  test('refresh preserves the loaded workspace scope', async () => {
    const storeState = makeState()
    storeState.workspaceId = 42

    await actions.refresh.call(
      { $client: {} },
      { commit: vi.fn(), state: storeState }
    )

    expect(aiProviderService).toHaveBeenCalledWith({}, 42)
  })

  test('update sends exactly the fields supplied by the form', async () => {
    const values = { is_active: false }
    await actions.update.call(
      { $client: {} },
      { commit: vi.fn() },
      { providerId: 1, values }
    )

    expect(service.update).toHaveBeenCalledWith(1, values)
    expect(service.update.mock.calls[0][1]).not.toHaveProperty('api_key')
  })

  test('model discovery gets known suggestions by provider type', async () => {
    const result = await actions.discoverModels.call(
      { $client: {} },
      {},
      'openai'
    )

    expect(service.discoverModels).toHaveBeenCalledWith('openai')
    expect(result).toEqual({ models: ['gpt-5.6'], supported: true })
  })

  test('model mutations preserve the provider and update only the model', () => {
    const state = makeState()
    state.providers = [{ id: 1, models: [{ id: 2, model_identifier: 'old' }] }]

    mutations.UPDATE_MODEL(state, { id: 2, model_identifier: 'new' })

    expect(state.providers).toEqual([
      { id: 1, models: [{ id: 2, model_identifier: 'new' }] },
    ])
  })

  test('one test action updates all returned saved model results', async () => {
    const committed = []
    const values = { model_ids: [2] }

    const results = await actions.testModels.call(
      { $client: {} },
      { commit: (type, payload) => committed.push([type, payload]) },
      values
    )

    expect(service.testModels).toHaveBeenCalledWith(values)
    expect(committed).toEqual([['UPDATE_MODEL_TEST_RESULTS', results]])

    const state = makeState()
    state.providers = [
      {
        id: 1,
        models: [
          {
            id: 2,
            last_test_status: null,
            last_test_error: '',
            last_test_at: null,
          },
        ],
      },
    ]
    mutations.UPDATE_MODEL_TEST_RESULTS(state, results)
    expect(state.providers[0].models[0]).toEqual({
      id: 2,
      last_test_status: 'success',
      last_test_error: '',
      last_test_at: '2026-07-21T12:00:00Z',
    })
  })
})
