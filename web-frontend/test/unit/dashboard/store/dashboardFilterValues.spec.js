import { createStore } from 'vuex'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import {
  TextFilterWidgetType,
  SummaryWidgetType,
} from '@baserow/modules/dashboard/widgetTypes'
import dashboardApplication from '@baserow/modules/dashboard/store/dashboardApplication'
import { WidgetDataProviderType } from '@baserow/modules/dashboard/dataProviderTypes'

const widget = {
  id: 12,
  type: 'text_filter',
  title: 'Search',
  default_value: 'Alpha',
  target_filters: [{ target_widget_id: 20 }, { target_widget_id: 22 }],
}
let store
let post
let requests
const source = (id) => ({ id })

beforeEach(() => {
  vi.useFakeTimers()
  requests = []
  post = vi.fn(
    (url, payload) =>
      new Promise((resolve) => requests.push({ url, payload, resolve }))
  )
  store = createStore({
    modules: {
      dashboardApplication,
      template: { namespaced: true, modules: { dashboardApplication } },
    },
  })
  store.$client = { post }
  const app = { $store: store, $i18n: { t: (key) => key } }
  const widgetTypes = {
    text_filter: new TextFilterWidgetType({ app }),
    summary: new SummaryWidgetType({ app }),
  }
  store.$registry = {
    get: (namespace, type) => widgetTypes[type],
    getAll: () => [new WidgetDataProviderType({ app: { $store: store } })],
  }
  store.commit('dashboardApplication/SET_DASHBOARD_ID', 42)
  store.dispatch('dashboardApplication/forceSetWidgets', [
    { ...widget },
    {
      ...widget,
      id: 13,
      default_value: '',
      target_filters: [{ target_widget_id: 21 }, { target_widget_id: 22 }],
    },
    { id: 20, type: 'summary', data_source_id: 1 },
    { id: 21, type: 'summary', data_source_id: 2 },
    { id: 22, type: 'summary', data_source_id: 3 },
    { id: 23, type: 'summary', data_source_id: 4 },
  ])
  store.commit('dashboardApplication/SET_DATA_SOURCES', [
    source(1),
    source(2),
    source(3),
    source(4),
  ])
})
afterEach(() => {
  store.commit('dashboardApplication/RESET')
  store.commit('template/dashboardApplication/RESET')
  vi.useRealTimers()
})
const change = (widgetId, value, prefix = '') =>
  store.dispatch(`${prefix}dashboardApplication/setWidgetValue`, {
    widgetId,
    value,
  })
const settle = async () => {
  requests
    .splice(0)
    .forEach(({ resolve }) => resolve({ data: { result: 'new' } }))
  await vi.advanceTimersByTimeAsync(0)
}

describe('Dashboard filter dispatch', () => {
  test('sends defaults on initial dispatch and selectively coalesces multiple inputs', async () => {
    const initial = store.dispatch('dashboardApplication/dispatchDataSource', 1)
    await vi.advanceTimersByTimeAsync(0)
    expect(requests[0].payload).toEqual({
      widget_data: { 12: 'Alpha', 13: '' },
    })
    await settle()
    await initial
    post.mockClear()
    await change(12, 'B')
    await vi.advanceTimersByTimeAsync(200)
    await change(12, 'Beta')
    await change(13, 'Other')
    expect(post).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(299)
    expect(post).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(requests.map(({ url }) => url)).toEqual([
      '/dashboard/data-sources/1/dispatch/',
      '/dashboard/data-sources/3/dispatch/',
      '/dashboard/data-sources/2/dispatch/',
    ])
    expect(requests.map(({ payload }) => payload)).toEqual(
      Array(3).fill({ widget_data: { 12: 'Beta', 13: 'Other' } })
    )
    await settle()
  })

  test('invalidates an older result immediately, before debounce fires, and sends clearing', async () => {
    const pending = store.dispatch('dashboardApplication/dispatchDataSource', 1)
    await vi.advanceTimersByTimeAsync(0)
    await change(12, '')
    requests.shift().resolve({ data: { result: 'stale' } })
    await pending
    expect(store.state.dashboardApplication.data[1]).not.toEqual({
      result: 'stale',
    })
    await vi.advanceTimersByTimeAsync(300)
    expect(requests[0].payload.widget_data[12]).toBe('')
    await settle()
    expect(store.state.dashboardApplication.data[1]).toEqual({ result: 'new' })
  })

  test('preserves values on unrelated realtime updates and resets changed defaults', async () => {
    await change(12, 'Typed')
    await vi.advanceTimersByTimeAsync(300)
    await settle()
    post.mockClear()
    await store.dispatch('dashboardApplication/handleWidgetUpdated', {
      ...widget,
      title: 'Renamed',
    })
    await vi.advanceTimersByTimeAsync(300)
    expect(post).not.toHaveBeenCalled()
    expect(store.state.dashboardApplication.widgetValues[12]).toBe('Typed')
    await store.dispatch('dashboardApplication/handleWidgetUpdated', {
      ...widget,
      default_value: 'Beta',
    })
    expect(store.state.dashboardApplication.widgetValues[12]).toBe('Beta')
    await vi.advanceTimersByTimeAsync(300)
    expect(requests).toHaveLength(2)
    await settle()
  })

  test('cancels pending work on navigation and isolates template values and timers', async () => {
    store.commit('template/dashboardApplication/SET_DASHBOARD_ID', 100)
    store.dispatch('template/dashboardApplication/forceSetWidgets', [
      { ...widget, target_filters: [{ target_widget_id: 25 }] },
      { id: 25, type: 'summary', data_source_id: 5 },
    ])
    store.commit('template/dashboardApplication/SET_DATA_SOURCES', [source(5)])
    await change(12, 'Private')
    await change(12, 'Template', 'template/')
    store.commit('dashboardApplication/RESET')
    await vi.advanceTimersByTimeAsync(300)
    expect(requests.map(({ payload }) => payload)).toEqual([
      { widget_data: { 12: 'Template' } },
    ])
    expect(requests[0].url).toBe('/dashboard/data-sources/5/dispatch/')
    await settle()
  })

  test('refreshes references to a deleted widget with the remaining viewer values', async () => {
    await store.dispatch('dashboardApplication/handleWidgetDeleted', 12)
    await vi.advanceTimersByTimeAsync(300)
    expect(requests).toHaveLength(2)
    expect(requests[0].payload).toEqual({ widget_data: { 13: '' } })
    await settle()
  })
  test('derives refreshes after input creation and target source changes', async () => {
    await store.dispatch('dashboardApplication/forceCreateWidget', {
      id: 24,
      type: 'summary',
      data_source_id: 6,
    })
    store.commit('dashboardApplication/ADD_DATA_SOURCE', source(6))
    await store.dispatch('dashboardApplication/handleNewWidgetCreated', {
      ...widget,
      id: 14,
      dashboard_id: 42,
      default_value: 'New filter',
      target_filters: [{ target_widget_id: 24 }],
    })
    expect(store.state.dashboardApplication.widgetValues[14]).toBe('New filter')
    await vi.advanceTimersByTimeAsync(300)
    expect(requests.map(({ url }) => url)).toEqual([
      '/dashboard/data-sources/6/dispatch/',
    ])
    await settle()
    await store.dispatch('dashboardApplication/handleWidgetUpdated', {
      id: 24,
      type: 'summary',
      data_source_id: 4,
    })
    await vi.advanceTimersByTimeAsync(300)
    expect(requests.map(({ url }) => url)).toEqual([
      '/dashboard/data-sources/6/dispatch/',
      '/dashboard/data-sources/4/dispatch/',
    ])
    await settle()
    await change(14, 'Changed')
    await vi.advanceTimersByTimeAsync(300)
    expect(requests.map(({ url }) => url)).toEqual([
      '/dashboard/data-sources/4/dispatch/',
    ])
    await settle()
  })

  test('sends public viewer input while retaining the dashboard password token', async () => {
    await store.dispatch('dashboardApplication/openPublicDashboard', {
      slug: 'public',
      authToken: 'password-token',
      dashboardId: 42,
      widgets: [
        {
          id: 12,
          type: 'text_filter',
          title: 'Search',
          default_value: 'Alpha',
          target_widget_ids: [20, 22],
        },
        {
          id: 13,
          type: 'text_filter',
          title: 'Other',
          default_value: '',
          target_widget_ids: [21, 22],
        },
        { id: 20, type: 'summary', data_source_id: 1 },
        { id: 21, type: 'summary', data_source_id: 2 },
        { id: 22, type: 'summary', data_source_id: 3 },
      ],
      dataSources: [source(1), source(2), source(3)],
    })
    await change(12, 'Beta')
    await vi.advanceTimersByTimeAsync(300)
    expect(requests.map(({ url }) => url)).toEqual([
      '/dashboard/public/public/data-sources/1/dispatch/',
      '/dashboard/public/public/data-sources/3/dispatch/',
    ])
    expect(requests[0].url).toBe(
      '/dashboard/public/public/data-sources/1/dispatch/'
    )
    expect(requests[0].payload).toEqual({ widget_data: { 12: 'Beta', 13: '' } })
    expect(post.mock.calls[0][2]).toEqual({
      headers: { 'Baserow-Dashboard-Authorization': 'JWT password-token' },
    })
    await settle()
  })
})

test('refreshes explicit constant-only targets after link edits and filter deletion', async () => {
  store.commit('dashboardApplication/SET_DATA_SOURCES', [source(1), source(2)])
  const group = {
    filters: [
      { field: 99, type: 'equal', value: { formula: 'Alpha', mode: 'raw' } },
    ],
    filter_groups: [],
    filter_type: 'AND',
  }
  store.dispatch('dashboardApplication/forceSetWidgets', [
    {
      ...widget,
      target_filters: [
        { target_widget_id: 20, group, empty_behavior: 'apply_nothing' },
      ],
    },
    { id: 20, type: 'summary', data_source_id: 1 },
    { id: 21, type: 'summary', data_source_id: 2 },
  ])
  await vi.advanceTimersByTimeAsync(300)
  await settle()
  await change(12, 'Beta')
  await vi.advanceTimersByTimeAsync(300)
  expect(requests.map(({ url }) => url)).toEqual([
    '/dashboard/data-sources/1/dispatch/',
  ])
  await settle()
  await store.dispatch('dashboardApplication/handleWidgetUpdated', {
    ...widget,
    target_filters: [
      { target_widget_id: 21, group, empty_behavior: 'apply_nothing' },
    ],
  })
  await vi.advanceTimersByTimeAsync(300)
  expect(requests.map(({ url }) => url).sort()).toEqual([
    '/dashboard/data-sources/1/dispatch/',
    '/dashboard/data-sources/2/dispatch/',
  ])
  await settle()
  await store.dispatch('dashboardApplication/handleWidgetDeleted', 12)
  await vi.advanceTimersByTimeAsync(300)
  expect(requests.map(({ url }) => url)).toEqual([
    '/dashboard/data-sources/2/dispatch/',
  ])
  await settle()
})
