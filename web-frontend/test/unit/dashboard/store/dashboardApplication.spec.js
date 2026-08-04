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
    }

    const fetchPromise = actions.fetchNewDataSources.call(
      { $client: {} },
      { commit, dispatch, getters },
      42
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

    expect(commit).toHaveBeenCalledWith('ADD_DATA_SOURCE', dataSource)
  })
})
