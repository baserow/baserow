import { afterEach, describe, expect, test, vi } from 'vitest'

import {
  actions,
  mutations,
  state as createState,
} from '@baserow/modules/dashboard/store/dashboardApplication'
import DataSourceService from '@baserow/modules/dashboard/services/dataSource'
import WidgetService from '@baserow/modules/dashboard/services/widget'

vi.mock('@baserow/modules/dashboard/services/dataSource', () => ({
  default: vi.fn(),
}))

vi.mock('@baserow/modules/dashboard/services/widget', () => ({
  default: vi.fn(),
}))

const deferred = () => {
  let resolve
  let reject
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })

  return { promise, resolve, reject }
}

const createDashboardState = (dashboardId = 42) => {
  const dashboardState = createState()
  mutations.SET_DASHBOARD_ID(dashboardState, dashboardId)
  return dashboardState
}

const applyCommit = (dashboardState) => {
  return vi.fn((mutation, payload) => {
    mutations[mutation](dashboardState, payload)
  })
}

describe('Dashboard application store', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  test('fetchNewDataSources waits for every data source to be dispatched', async () => {
    const dashboardState = createDashboardState()
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
    const commit = applyCommit(dashboardState)
    const getters = {
      getDataSourceById: (dataSourceId) => {
        return dashboardState.dataSources.find(
          (existingDataSource) => existingDataSource.id === dataSourceId
        )
      },
    }

    const fetchPromise = actions.fetchNewDataSources.call(
      { $client: {} },
      { state: dashboardState, commit, dispatch, getters },
      42
    )

    await vi.waitFor(() => {
      expect(dispatch).toHaveBeenCalledWith(
        'dispatchDataSource',
        expect.objectContaining({ dataSourceId: 1 })
      )
    })

    let completed = false
    void fetchPromise.then(() => {
      completed = true
    })
    await Promise.resolve()
    expect(completed).toBe(false)

    resolveDispatch()
    await fetchPromise

    expect(dashboardState.dataSources).toEqual([dataSource])
  })

  test('deleteWidget reloads the canonical widget layout after deletion', async () => {
    const dashboardState = createDashboardState()
    const deleteWidget = vi.fn().mockResolvedValue()
    WidgetService.mockReturnValue({ delete: deleteWidget })
    const dispatch = vi.fn().mockResolvedValue()
    const commit = applyCommit(dashboardState)

    await actions.deleteWidget.call(
      { $client: {} },
      { state: dashboardState, commit, dispatch },
      1
    )

    expect(deleteWidget).toHaveBeenCalledWith(1)
    expect(dispatch).toHaveBeenCalledWith('fetchWidgets', 42)
  })

  test('fetchWidgets replaces the current widgets with the filtered API result', async () => {
    const dashboardState = createDashboardState()
    const widgets = [
      { id: 2, grid_x: 2, grid_y: 0, grid_width: 4, grid_height: 4 },
    ]
    const getAllWidgets = vi.fn().mockResolvedValue({ data: widgets })
    WidgetService.mockReturnValue({ getAllWidgets })
    const commit = applyCommit(dashboardState)

    const result = await actions.fetchWidgets.call(
      { $client: {} },
      { state: dashboardState, commit },
      42
    )

    expect(getAllWidgets).toHaveBeenCalledWith(42)
    expect(dashboardState.widgets).toEqual(widgets)
    expect(result).toEqual(widgets)
  })

  test('keeps only the latest concurrent widget fetch', async () => {
    const dashboardState = createDashboardState()
    const firstRequest = deferred()
    const secondRequest = deferred()
    const getAllWidgets = vi
      .fn()
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)
    WidgetService.mockReturnValue({ getAllWidgets })
    const commit = applyCommit(dashboardState)
    const context = { state: dashboardState, commit }

    const firstFetch = actions.fetchWidgets.call({ $client: {} }, context, 42)
    const secondFetch = actions.fetchWidgets.call({ $client: {} }, context, 42)

    const newestWidgets = [{ id: 2, title: 'Newest' }]
    secondRequest.resolve({ data: newestWidgets })
    await secondFetch
    firstRequest.resolve({ data: [{ id: 1, title: 'Stale' }] })
    await firstFetch

    expect(dashboardState.widgets).toEqual(newestWidgets)
  })

  test('ignores a widget response received after dashboard navigation', async () => {
    const dashboardState = createDashboardState()
    const request = deferred()
    WidgetService.mockReturnValue({
      getAllWidgets: vi.fn().mockReturnValue(request.promise),
    })
    const commit = applyCommit(dashboardState)

    const fetchPromise = actions.fetchWidgets.call(
      { $client: {} },
      { state: dashboardState, commit },
      42
    )
    mutations.RESET(dashboardState)
    mutations.SET_DASHBOARD_ID(dashboardState, 99)
    request.resolve({ data: [{ id: 1, title: 'Old dashboard' }] })
    await fetchPromise

    expect(dashboardState.dashboardId).toBe(99)
    expect(dashboardState.widgets).toEqual([])
  })

  test('ignores data sources received after dashboard navigation', async () => {
    const dashboardState = createDashboardState()
    const request = deferred()
    DataSourceService.mockReturnValue({
      getAllDataSources: vi.fn().mockReturnValue(request.promise),
    })
    const commit = applyCommit(dashboardState)
    const dispatch = vi.fn().mockResolvedValue()

    const fetchPromise = actions.fetchNewDataSources.call(
      { $client: {} },
      {
        state: dashboardState,
        commit,
        dispatch,
        getters: { getDataSourceById: () => undefined },
      },
      42
    )
    mutations.RESET(dashboardState)
    mutations.SET_DASHBOARD_ID(dashboardState, 99)
    request.resolve({ data: [{ id: 7, name: 'Old dashboard source' }] })
    await fetchPromise

    expect(dashboardState.dataSources).toEqual([])
    expect(dispatch).not.toHaveBeenCalled()
  })

  test('dispatches data for the latest concurrent data source fetch', async () => {
    const dashboardState = createDashboardState()
    const firstDispatch = deferred()
    const dataSource = { id: 7, name: 'Source' }
    const getAllDataSources = vi.fn().mockResolvedValue({ data: [dataSource] })
    DataSourceService.mockReturnValue({ getAllDataSources })
    const commit = applyCommit(dashboardState)
    let dispatchCount = 0
    const dispatch = vi.fn().mockImplementation((action, request) => {
      if (action === 'dispatchDataSource') {
        dispatchCount += 1
        if (dispatchCount === 1) {
          mutations.UPDATE_DATA(dashboardState, {
            dataSourceId: request.dataSourceId,
            values: null,
          })
          return firstDispatch.promise
        }
        mutations.UPDATE_DATA(dashboardState, {
          dataSourceId: request.dataSourceId,
          values: { count: 1 },
        })
      }
      return Promise.resolve()
    })
    const getters = {
      getDataSourceById: (id) =>
        dashboardState.dataSources.find((source) => source.id === id),
    }
    const context = { state: dashboardState, commit, dispatch, getters }

    const firstFetch = actions.fetchNewDataSources.call(
      { $client: {} },
      context,
      42
    )
    await vi.waitFor(() => expect(dispatch).toHaveBeenCalledTimes(1))
    const secondFetch = actions.fetchNewDataSources.call(
      { $client: {} },
      context,
      42
    )
    await secondFetch
    firstDispatch.resolve()
    await firstFetch

    expect(dispatch).toHaveBeenCalledTimes(2)
    expect(dispatch).toHaveBeenLastCalledWith(
      'dispatchDataSource',
      expect.objectContaining({ dataSourceId: 7 })
    )
    expect(dashboardState.data[7]).toEqual({ count: 1 })
  })

  test('does not add a temporary widget while its server layout is being created', async () => {
    const dashboardState = createDashboardState()
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
    const commit = applyCommit(dashboardState)
    const dispatch = vi.fn()
    dispatch.mockImplementation((action, payload) => {
      if (action === 'handleNewWidgetCreated') {
        return actions.handleNewWidgetCreated(
          { state: dashboardState, commit, dispatch },
          payload
        )
      }
      return Promise.resolve()
    })

    const createWidgetPromise = actions.createWidget.call(
      { $client: {} },
      { state: dashboardState, commit, dispatch },
      { dashboard, widget }
    )

    expect(commit).not.toHaveBeenCalled()

    resolveCreateWidget({ data: createdWidget })
    await createWidgetPromise

    expect(dispatch).toHaveBeenCalledWith(
      'handleNewWidgetCreated',
      createdWidget
    )
    expect(dashboardState.widgets).toEqual([createdWidget])
  })

  test('retries rejected secondary refreshes once after creating a widget', async () => {
    const dashboardState = createDashboardState()
    const dashboard = { id: 42 }
    const createdWidget = {
      id: 1,
      dashboard_id: dashboard.id,
      title: 'Summary',
      type: 'summary',
    }
    const create = vi.fn().mockResolvedValue({ data: createdWidget })
    WidgetService.mockReturnValue({ create })
    const commit = applyCommit(dashboardState)
    let dataSourceRefreshes = 0
    const dispatch = vi.fn((action, payload) => {
      if (action === 'handleNewWidgetCreated') {
        return actions.handleNewWidgetCreated(
          { state: dashboardState, commit, dispatch },
          payload
        )
      }
      if (action === 'fetchNewDataSources') {
        dataSourceRefreshes += 1
        return dataSourceRefreshes === 1
          ? Promise.reject(new Error('Refresh failed'))
          : Promise.resolve()
      }
      return Promise.resolve()
    })

    await expect(
      actions.createWidget.call(
        { $client: {} },
        { state: dashboardState, commit, dispatch },
        {
          dashboard,
          widget: { title: 'Summary', type: 'summary' },
        }
      )
    ).resolves.toEqual(createdWidget)

    expect(dashboardState.widgets).toEqual([createdWidget])
    expect(dataSourceRefreshes).toBe(2)
    expect(dispatch).toHaveBeenCalledWith(
      'application/refreshPermissions',
      dashboard,
      { root: true }
    )
  })

  test('refetches filtered widgets and data sources after a layout invalidation', async () => {
    const dashboardState = createDashboardState()
    const dispatch = vi.fn().mockRejectedValue(new Error('Refresh failed'))
    const commit = applyCommit(dashboardState)

    await expect(
      actions.handleWidgetsLayoutUpdated({
        state: dashboardState,
        commit,
        dispatch,
      })
    ).resolves.toBeUndefined()

    expect(dispatch).toHaveBeenCalledWith('fetchWidgets', 42)
    expect(dispatch).toHaveBeenCalledWith('fetchNewDataSources', 42)
  })

  test('refetches canonical widgets for an update received during initial loading', async () => {
    const dashboardState = createDashboardState()
    dashboardState.loading = true
    const commit = applyCommit(dashboardState)
    const dispatch = vi.fn().mockResolvedValue()

    await actions.handleWidgetUpdated(
      { state: dashboardState, commit, dispatch },
      { id: 1, title: 'Updated while loading' }
    )

    expect(dispatch).toHaveBeenCalledWith('fetchWidgets', 42)
    expect(dashboardState.widgets).toEqual([])
  })

  test('upserts a data source update that arrives before its initial fetch', () => {
    const dashboardState = createDashboardState()

    mutations.UPDATE_DATA_SOURCE(dashboardState, {
      dataSourceId: 7,
      values: { id: 7, name: 'Realtime source' },
    })

    expect(dashboardState.dataSources).toEqual([
      { id: 7, name: 'Realtime source' },
    ])
  })

  test('does not add a created widget after navigating away', async () => {
    const dashboardState = createDashboardState()
    const createRequest = deferred()
    WidgetService.mockReturnValue({
      create: vi.fn().mockReturnValue(createRequest.promise),
    })
    const dispatch = vi.fn().mockResolvedValue()
    const dashboard = { id: 42 }

    const createPromise = actions.createWidget.call(
      { $client: {} },
      { state: dashboardState, dispatch },
      {
        dashboard,
        widget: { title: 'Summary', type: 'summary' },
      }
    )
    mutations.RESET(dashboardState)
    mutations.SET_DASHBOARD_ID(dashboardState, 99)
    const createdWidget = { id: 1, dashboard_id: 42, type: 'summary' }
    createRequest.resolve({ data: createdWidget })

    await expect(createPromise).resolves.toEqual(createdWidget)
    expect(dispatch).not.toHaveBeenCalled()
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
