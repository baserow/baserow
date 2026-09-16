import { expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import MockAdapter from 'axios-mock-adapter'

describe('dashboardApplication store', () => {
  const dashboardId = 1
  const dataSource = {
    id: 10,
    dashboard_id: dashboardId,
    type: 'local_baserow_aggregate_rows',
  }
  const dataSourceResult = { result: 42 }
  const createdWidget = {
    id: 5,
    dashboard_id: dashboardId,
    type: 'summary',
    data_source_id: dataSource.id,
  }

  let store = null
  let mock = null

  beforeEach(async () => {
    const { $store, $client } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })

    mock.onGet(`/dashboard/${dashboardId}/widgets/`).reply(200, [])
    mock.onGet(`/dashboard/${dashboardId}/data-sources/`).replyOnce(200, [])
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId,
      forEditing: false,
    })

    // The data source that belongs to the widget created afterwards.
    mock
      .onGet(`/dashboard/${dashboardId}/data-sources/`)
      .reply(200, [dataSource])
    mock
      .onPost(`/dashboard/data-sources/${dataSource.id}/dispatch/`)
      .reply(200, dataSourceResult)
  })

  afterEach(() => {
    mock.restore()
  })

  test('fetchNewDataSources awaits missing results for an existing source', async () => {
    store.commit('dashboardApplication/ADD_DATA_SOURCE', dataSource)
    let completeDispatch
    mock.onPost(`/dashboard/data-sources/${dataSource.id}/dispatch/`).reply(
      () =>
        new Promise((resolve) => {
          completeDispatch = resolve
        })
    )

    let refreshCompleted = false
    const refresh = store
      .dispatch('dashboardApplication/fetchNewDataSources', {
        dashboardId,
        requestId: store.state.dashboardApplication.fetchRequestId,
      })
      .then(() => {
        refreshCompleted = true
      })
    await flushPromises()

    expect(mock.history.post).toHaveLength(1)
    expect(refreshCompleted).toBe(false)
    expect(store.state.dashboardApplication.dataSources).toHaveLength(1)

    completeDispatch([200, dataSourceResult])
    await refresh

    expect(refreshCompleted).toBe(true)
    expect({
      dataSources: store.state.dashboardApplication.dataSources,
      data: store.state.dashboardApplication.data,
    }).toMatchSnapshot()
  })

  test('fetchNewDataSources preserves cached results without dispatching again', async () => {
    store.commit('dashboardApplication/ADD_DATA_SOURCE', dataSource)
    store.commit('dashboardApplication/UPDATE_DATA', {
      dataSourceId: dataSource.id,
      values: dataSourceResult,
    })

    await store.dispatch('dashboardApplication/fetchNewDataSources', {
      dashboardId,
      requestId: store.state.dashboardApplication.fetchRequestId,
    })

    expect(mock.history.post).toHaveLength(0)
    expect({
      dataSources: store.state.dashboardApplication.dataSources,
      data: store.state.dashboardApplication.data,
    }).toMatchSnapshot()
  })

  test('handleNewWidgetCreated replaces the optimistic widget and fetches its data source', async () => {
    const tempWidgetId = 99999
    store.commit('dashboardApplication/ADD_WIDGET', {
      id: tempWidgetId,
      type: 'summary',
    })

    await store.dispatch('dashboardApplication/handleNewWidgetCreated', {
      tempWidgetId,
      createdWidget,
    })
    await flushPromises()

    expect(mock.history.get.map((request) => request.url)).toContain(
      `/dashboard/${dashboardId}/data-sources/`
    )
    expect(
      store.getters['dashboardApplication/getWidgetById'](tempWidgetId)
    ).toBeUndefined()
    expect(
      store.getters['dashboardApplication/getWidgetById'](createdWidget.id)
    ).toMatchObject(createdWidget)
    expect(store.getters['dashboardApplication/getSelectedWidgetId']).toBe(
      createdWidget.id
    )
    expect(
      store.getters['dashboardApplication/getDataSourceById'](dataSource.id)
    ).toMatchObject(dataSource)
    expect(store.state.dashboardApplication.data[dataSource.id]).toEqual(
      dataSourceResult
    )
  })

  test('handleNewWidgetCreated adds a widget created elsewhere without selecting it', async () => {
    await store.dispatch('dashboardApplication/handleNewWidgetCreated', {
      createdWidget,
    })
    await flushPromises()

    expect(store.state.dashboardApplication.widgets).toHaveLength(1)
    expect(
      store.getters['dashboardApplication/getWidgetById'](createdWidget.id)
    ).toMatchObject(createdWidget)
    expect(store.getters['dashboardApplication/getSelectedWidgetId']).toBe(null)
    expect(
      store.getters['dashboardApplication/getDataSourceById'](dataSource.id)
    ).toMatchObject(dataSource)
    expect(store.state.dashboardApplication.data[dataSource.id]).toEqual(
      dataSourceResult
    )
  })
})
