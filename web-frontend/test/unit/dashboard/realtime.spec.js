import { registerRealtimeEvents } from '@baserow/modules/dashboard/realtime'

const getHandlers = () => {
  const handlers = {}
  registerRealtimeEvents({
    registerEvent: (name, handler) => {
      handlers[name] = handler
    },
  })
  return handlers
}

const buildStore = (dashboardId = 42) => ({
  getters: {
    'dashboardApplication/getDashboardId': dashboardId,
  },
  dispatch: vi.fn().mockResolvedValue(),
})

describe('dashboard realtime', () => {
  test('refetches permission-filtered state after a layout invalidation', async () => {
    const handlers = getHandlers()
    const store = buildStore()

    await handlers.widgets_layout_updated(
      { store },
      {
        dashboard_id: 42,
      }
    )

    expect(store.dispatch).toHaveBeenCalledWith(
      'dashboardApplication/handleWidgetsLayoutUpdated'
    )
  })

  test('does not refresh an unrelated dashboard', async () => {
    const handlers = getHandlers()
    const store = buildStore()

    await handlers.widgets_layout_updated(
      { store },
      {
        dashboard_id: 99,
      }
    )

    expect(store.dispatch).not.toHaveBeenCalled()
  })

  test('loads the data source after a widget is created remotely', async () => {
    const handlers = getHandlers()
    const store = buildStore()
    const widget = { id: 1, dashboard_id: 42 }

    await handlers.widget_created(
      { store },
      {
        dashboard_id: 42,
        widget,
      }
    )

    expect(store.dispatch).toHaveBeenNthCalledWith(
      1,
      'dashboardApplication/handleNewWidgetCreated',
      widget
    )
    expect(store.dispatch).toHaveBeenNthCalledWith(
      2,
      'dashboardApplication/fetchWidgets',
      42
    )
    expect(store.dispatch).toHaveBeenNthCalledWith(
      3,
      'dashboardApplication/fetchNewDataSources',
      42
    )
  })

  test('does not refresh old widget data sources after navigation', async () => {
    const handlers = getHandlers()
    let dashboardId = 42
    const store = {
      getters: {},
      dispatch: vi.fn().mockImplementationOnce(async () => {
        dashboardId = 99
      }),
    }
    Object.defineProperty(
      store.getters,
      'dashboardApplication/getDashboardId',
      { get: () => dashboardId }
    )

    await handlers.widget_created(
      { store },
      {
        dashboard_id: 42,
        widget: { id: 1, dashboard_id: 42 },
      }
    )

    expect(store.dispatch).toHaveBeenCalledTimes(1)
  })
})
