import { expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import MockAdapter from 'axios-mock-adapter'
import { registerRealtimeEvents } from '@baserow/modules/dashboard/realtime'

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
  let events = null

  beforeEach(async () => {
    const { $store, $client } = useNuxtApp()
    store = $store
    mock = new MockAdapter($client, { onNoMatch: 'throwException' })
    events = {}
    registerRealtimeEvents({
      registerEvent: (name, callback) => {
        events[name] = callback
      },
    })

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

  test('local creation selects the persisted widget and fetches its data source', async () => {
    mock.onPost(`/dashboard/${dashboardId}/widgets/`).reply(200, createdWidget)
    await store.dispatch('dashboardApplication/createWidget', {
      dashboard: { id: dashboardId },
      widget: { type: 'summary' },
    })
    await flushPromises()

    expect(mock.history.get.map((request) => request.url)).toContain(
      `/dashboard/${dashboardId}/data-sources/`
    )
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

  test('realtime adds a widget created elsewhere without selecting it', async () => {
    mock.onGet(`/dashboard/${dashboardId}/widgets/`).reply(200, [createdWidget])
    await events.widget_created(
      { store },
      {
        dashboard_id: dashboardId,
        widget: createdWidget,
      }
    )
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

  test.each(['local', 'realtime'])(
    '%s creation keeps an existing unconfigured widget out of loading',
    async (creation) => {
      const existingDataSource = { ...dataSource, id: 20 }
      const existingWidget = {
        ...createdWidget,
        id: 6,
        data_source_id: existingDataSource.id,
      }
      mock
        .onGet(`/dashboard/${dashboardId}/widgets/`)
        .reply(200, [existingWidget])
      mock
        .onGet(`/dashboard/${dashboardId}/data-sources/`)
        .reply(200, [existingDataSource])
      mock
        .onPost(`/dashboard/data-sources/${existingDataSource.id}/dispatch/`)
        .reply(400, { error: 'ERROR_SERVICE_INVALID' })
      await store.dispatch('dashboardApplication/fetchInitial', {
        dashboardId,
        forEditing: false,
      })

      const widgetType = useNuxtApp().$registry.get(
        'dashboardWidget',
        'summary'
      )
      expect(
        widgetType.isMisconfigured(
          existingWidget,
          store.state.dashboardApplication.data
        )
      ).toBe(true)
      const loadingStates = []
      const unsubscribe = store.subscribe((_mutation, state) => {
        loadingStates.push(
          widgetType.isLoading(existingWidget, state.dashboardApplication.data)
        )
      })
      mock
        .onGet(`/dashboard/${dashboardId}/data-sources/`)
        .reply(200, [existingDataSource, dataSource])

      try {
        if (creation === 'local') {
          mock
            .onPost(`/dashboard/${dashboardId}/widgets/`)
            .reply(200, createdWidget)
          await store.dispatch('dashboardApplication/createWidget', {
            dashboard: { id: dashboardId },
            widget: { type: 'summary' },
          })
        } else {
          mock
            .onGet(`/dashboard/${dashboardId}/widgets/`)
            .reply(200, [existingWidget, createdWidget])
          await events.widget_created(
            { store },
            { dashboard_id: dashboardId, widget: createdWidget }
          )
        }
        await flushPromises()

        expect(loadingStates.length).toBeGreaterThan(0)
        expect(loadingStates).not.toContain(true)
        expect(store.state.dashboardApplication.data[dataSource.id]).toEqual(
          dataSourceResult
        )
      } finally {
        unsubscribe()
      }

      const configuredDataSource = { ...existingDataSource, table_id: 1 }
      mock
        .onPatch(`/dashboard/data-sources/${existingDataSource.id}/`)
        .reply(200, configuredDataSource)
      mock
        .onPost(`/dashboard/data-sources/${existingDataSource.id}/dispatch/`)
        .reply(200, dataSourceResult)
      await store.dispatch('dashboardApplication/updateDataSource', {
        dataSourceId: existingDataSource.id,
        values: { table_id: 1 },
      })
      expect(
        store.state.dashboardApplication.data[existingDataSource.id]
      ).toEqual(dataSourceResult)
    }
  )
})
