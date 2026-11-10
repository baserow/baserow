import { createStore } from 'vuex'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import dashboardApplication from '@baserow/modules/dashboard/store/dashboardApplication'
import { TextFilterWidgetType } from '@baserow/modules/dashboard/widgetTypes'

let store
let hasPermission
beforeEach(() => {
  vi.useFakeTimers()
  store = createStore({
    modules: { dashboardApplication },
    getters: {
      'application/get': () => () => ({ id: 42, workspace: { id: 1 } }),
    },
  })
  hasPermission = vi.fn(() => true)
  const type = new TextFilterWidgetType({
    app: {
      $store: store,
      $hasPermission: hasPermission,
      $i18n: { t: (key) => key },
    },
  })
  store.$registry = { get: () => type }
  store.$client = {
    get: vi.fn(),
    patch: vi.fn(async () => ({ data: {} })),
  }
  store.commit('dashboardApplication/SET_DASHBOARD_ID', 42)
})
afterEach(() => {
  store.commit('dashboardApplication/RESET')
  vi.useRealTimers()
})
const seed = (multiple = true, defaultValue = ['France', 'Belgium']) =>
  store.dispatch('dashboardApplication/forceSetWidgets', [
    {
      id: 12,
      type: 'text_filter',
      mode: 'dropdown',
      multiple,
      options: {
        formula: "get('data_source_context.1.field_10.*.value')",
        mode: 'advanced',
      },
      default_value: defaultValue,
      target_filters: [],
    },
  ])
const reconcile = (available = ['France']) =>
  store.dispatch('dashboardApplication/reconcileWidgetOptions', {
    widgetId: 12,
    options: available,
  })
const state = () => store.state.dashboardApplication

test.each([
  [true, ['France', 'Belgium'], ['France'], ['France']],
  [true, ['France', 'Belgium'], [], []],
  [false, 'Belgium', ['France'], ''],
  [true, ['France'], ['France', 'Belgium'], ['France']],
])(
  'reconciles defaults and selection without mounting settings (%s, %j, %j)',
  async (multiple, initial, available, expected) => {
    await seed(multiple, initial)
    const loading = reconcile(available)
    await vi.advanceTimersByTimeAsync(1000)
    await loading
    expect(state().widgets[0].default_value).toEqual(expected)
    expect(state().widgetValues[12]).toEqual(expected)
    if (JSON.stringify(initial) === JSON.stringify(expected))
      expect(store.$client.patch).not.toHaveBeenCalled()
    else
      expect(store.$client.patch).toHaveBeenCalledWith(
        '/dashboard/widgets/12/',
        { default_value: expected }
      )
    await reconcile()
    expect(store.$client.get).not.toHaveBeenCalled()
  }
)

test.each(['viewer', 'public'])(
  'prunes unavailable values locally for %s without saving',
  async (access) => {
    await seed()
    hasPermission.mockReturnValue(false)
    if (access === 'public')
      store.commit('dashboardApplication/SET_PUBLIC', {
        slug: 'shared',
        authToken: null,
      })
    await reconcile()
    expect(state().widgets[0].default_value).toEqual(['France'])
    expect(state().widgetValues[12]).toEqual(['France'])
    expect(store.$client.patch).not.toHaveBeenCalled()
  }
)

test('preserves a valid active selection when cleaning up defaults', async () => {
  await seed()
  await store.dispatch('dashboardApplication/setWidgetValue', {
    widgetId: 12,
    value: ['Italy'],
  })
  const loading = reconcile(['France', 'Italy'])
  await vi.advanceTimersByTimeAsync(1000)
  await loading
  expect(state().widgets[0].default_value).toEqual(['France'])
  expect(state().widgetValues[12]).toEqual(['Italy'])
})
