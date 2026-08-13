import { afterEach, describe, expect, test, vi } from 'vitest'

import {
  actions,
  mutations,
} from '@baserow/modules/dashboard/store/dashboardApplication'
import DataSourceService from '@baserow/modules/dashboard/services/dataSource'
import WidgetService from '@baserow/modules/dashboard/services/widget'

vi.mock('@baserow/modules/dashboard/services/dataSource', () => ({
  default: vi.fn(),
}))

vi.mock('@baserow/modules/dashboard/services/widget', () => ({
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

  test('deleteWidget reloads the canonical widget layout after deletion', async () => {
    const deleteWidget = vi.fn().mockResolvedValue()
    const getAllWidgets = vi.fn().mockResolvedValue({
      data: [{ id: 2, grid_x: 2, grid_y: 0, grid_width: 4, grid_height: 4 }],
    })
    WidgetService.mockReturnValue({ delete: deleteWidget, getAllWidgets })
    const commit = vi.fn()

    await actions.deleteWidget.call(
      { $client: {} },
      { state: { dashboardId: 42 }, commit },
      1
    )

    expect(deleteWidget).toHaveBeenCalledWith(1)
    expect(getAllWidgets).toHaveBeenCalledWith(42)
    expect(commit).toHaveBeenCalledWith('SET_WIDGETS', [
      { id: 2, grid_x: 2, grid_y: 0, grid_width: 4, grid_height: 4 },
    ])
  })

  test('does not add a temporary widget while its server layout is being created', async () => {
    let resolveCreateWidget
    const create = vi.fn(
      () =>
        new Promise((resolve) => {
          resolveCreateWidget = resolve
        })
    )
    WidgetService.mockReturnValue({ create })

    const dashboard = { id: 42 }
    const widget = { title: 'Summary', type: 'summary' }
    const createdWidget = {
      id: 1,
      dashboard_id: dashboard.id,
      ...widget,
      grid_x: 2,
      grid_y: 0,
      grid_width: 2,
      grid_height: 4,
    }
    const commit = vi.fn()
    const dispatch = vi.fn()
    dispatch.mockImplementation((action, payload) => {
      if (action === 'handleNewWidgetCreated') {
        return actions.handleNewWidgetCreated({ commit, dispatch }, payload)
      }
      return Promise.resolve()
    })

    const createWidgetPromise = actions.createWidget.call(
      { $client: {} },
      { commit, dispatch },
      { dashboard, widget }
    )

    expect(commit).not.toHaveBeenCalled()

    resolveCreateWidget({ data: createdWidget })
    await createWidgetPromise

    expect(dispatch).toHaveBeenCalledWith(
      'handleNewWidgetCreated',
      createdWidget
    )
    expect(commit).toHaveBeenCalledWith('ADD_WIDGET', createdWidget)
  })

  test('does not add a partial widget update for an unknown widget', () => {
    const state = {
      widgets: [{ id: 1, title: 'Existing widget' }],
    }

    mutations.UPDATE_WIDGET(state, {
      widgetId: 2,
      values: { title: 'Partial widget update' },
    })

    expect(state.widgets).toEqual([{ id: 1, title: 'Existing widget' }])
  })
})
