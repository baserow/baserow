import { afterEach, describe, expect, test, vi } from 'vitest'

import { actions } from '@baserow/modules/dashboard/store/dashboardApplication'
import DataSourceService from '@baserow/modules/dashboard/services/dataSource'

vi.mock('@baserow/modules/dashboard/services/dataSource', () => ({
  default: vi.fn(),
}))

describe('Dashboard application store', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  test('fetchNewDataSources waits for every data source to be dispatched', async () => {
    const dataSource = { id: 1 }
    const getAllDataSources = vi.fn().mockResolvedValue({
      data: [dataSource],
    })
    DataSourceService.mockReturnValue({ getAllDataSources })

    let resolveDispatch
    const dispatchPromise = new Promise((resolve) => {
      resolveDispatch = resolve
    })
    const dispatch = vi.fn().mockReturnValue(dispatchPromise)
    const commit = vi.fn()
    const getters = {
      getDataSourceById: vi.fn().mockReturnValue(undefined),
      getDataForDataSource: vi.fn().mockReturnValue(undefined),
    }

    const fetchPromise = actions.fetchNewDataSources.call(
      { $client: {} },
      { commit, dispatch, getters, state: { fetchRequestId: 1 } },
      { dashboardId: 42, requestId: 1 }
    )

    await vi.waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith('dispatchDataSource', 1)
    })

    let completed = false
    void fetchPromise.then(() => {
      completed = true
    })
    await Promise.resolve()
    expect(completed).toBe(false)

    resolveDispatch()
    await fetchPromise

    expect(getAllDataSources).toHaveBeenCalledWith(42)
    expect(commit).toHaveBeenCalledWith('ADD_DATA_SOURCE', dataSource)
  })

  test('ignores data sources when a newer dashboard fetch supersedes the request', async () => {
    let resolveRequest
    DataSourceService.mockReturnValue({
      getAllDataSources: vi.fn().mockReturnValue(
        new Promise((resolve) => {
          resolveRequest = resolve
        })
      ),
    })
    const state = { fetchRequestId: 1 }
    const commit = vi.fn()
    const dispatch = vi.fn()
    const fetchPromise = actions.fetchNewDataSources.call(
      { $client: {} },
      { commit, dispatch, getters: { getDataSourceById: vi.fn() }, state },
      { dashboardId: 42, requestId: 1 }
    )

    state.fetchRequestId = 2
    resolveRequest({ data: [{ id: 1 }] })
    await fetchPromise

    expect(commit).not.toHaveBeenCalled()
    expect(dispatch).not.toHaveBeenCalled()
  })

  test('creating a widget fetches its data sources with the current request ID', async () => {
    const dispatch = vi.fn()
    const widget = { id: 1, dashboard_id: 42 }
    await actions.handleNewWidgetCreated.call(
      {},
      {
        commit: vi.fn(),
        dispatch,
        getters: { getWidgetById: vi.fn() },
        state: { fetchRequestId: 3 },
      },
      widget
    )

    expect(dispatch).toHaveBeenCalledWith('fetchNewDataSources', {
      dashboardId: 42,
      requestId: 3,
    })
  })
})
