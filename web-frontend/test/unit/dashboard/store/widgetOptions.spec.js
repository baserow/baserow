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
    get: vi.fn(async () => ({ data: { results: ['France'] } })),
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
        mode: 'formula',
      },
      default_value: defaultValue,
      target_filters: [],
    },
  ])
const load = (force = false) =>
  store.dispatch('dashboardApplication/fetchWidgetOptions', {
    widgetId: 12,
    force,
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
    store.$client.get.mockResolvedValue({ data: { results: available } })
    const loading = load()
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
    await load()
    expect(store.$client.get).toHaveBeenCalledTimes(1)
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
    await load()
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
  store.$client.get.mockResolvedValue({
    data: { results: ['France', 'Italy'] },
  })
  const loading = load()
  await vi.advanceTimersByTimeAsync(1000)
  await loading
  expect(state().widgets[0].default_value).toEqual(['France'])
  expect(state().widgetValues[12]).toEqual(['Italy'])
})

test.each(['failure', 'options changed', 'dashboard changed'])(
  'does not prune defaults during loading or after %s',
  async (outcome) => {
    await seed()
    let resolve, reject
    store.$client.get.mockReturnValue(
      new Promise((res, rej) => {
        resolve = res
        reject = rej
      })
    )
    const loading = load()
    expect(state().widgets[0].default_value).toEqual(['France', 'Belgium'])
    expect(state().widgetValues[12]).toEqual(['France', 'Belgium'])
    if (outcome === 'failure') reject(new Error('Unavailable'))
    else {
      if (outcome === 'options changed')
        store.commit('dashboardApplication/UPDATE_WIDGET', {
          widgetId: 12,
          values: { options: { formula: 'Italy' } },
        })
      else store.commit('dashboardApplication/RESET')
      resolve({ data: { results: [] } })
    }
    await loading
    if (outcome !== 'dashboard changed')
      expect(state().widgets[0].default_value).toEqual(['France', 'Belgium'])
    expect(store.$client.patch).not.toHaveBeenCalled()
  }
)
