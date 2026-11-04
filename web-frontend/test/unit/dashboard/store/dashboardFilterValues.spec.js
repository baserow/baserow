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
  test('rolls back an automatic selection after another widget saves', async () => {
    const serverWidgets = JSON.parse(
      JSON.stringify(store.state.dashboardApplication.widgets)
    )
    const finish = {}
    store.$client.patch = vi.fn(
      (url) =>
        new Promise((resolve, reject) => {
          finish[url] = { resolve, reject }
        })
    )
    store.$client.get = vi.fn(async () => ({ data: serverWidgets }))
    const savingDefault = store
      .dispatch('dashboardApplication/updateWidget', {
        widgetId: 13,
        values: { default_value: 'Gamma' },
        originalValues: { default_value: '' },
      })
      .catch(() => {})
    const savingTitle = store.dispatch('dashboardApplication/updateWidget', {
      widgetId: 23,
      values: { title: 'Renamed' },
      originalValues: { title: '' },
    })
    await vi.advanceTimersByTimeAsync(1000)
    finish['/dashboard/widgets/23/'].resolve({ data: {} })
    await savingTitle
    finish['/dashboard/widgets/13/'].reject(new Error('Save failed'))
    await savingDefault
    expect(
      store.state.dashboardApplication.widgets.find(({ id }) => id === 13)
        .default_value
    ).toBe('')
    expect(store.state.dashboardApplication.widgetValues[13]).toBe('')
    await vi.advanceTimersByTimeAsync(300)
    expect(
      requests.filter(({ payload }) => payload.widget_data[13] === 'Gamma')
    ).toEqual([])
    await settle()
  })

  test('does not roll back the selection of a newer completed save of the same widget', async () => {
    const finish = []
    const serverWidgets = JSON.parse(
      JSON.stringify(store.state.dashboardApplication.widgets)
    )
    store.$client.patch = vi.fn(
      () => new Promise((resolve, reject) => finish.push({ resolve, reject }))
    )
    store.$client.get = vi.fn(async () => ({ data: serverWidgets }))
    const first = store
      .dispatch('dashboardApplication/updateWidget', {
        widgetId: 13,
        values: { default_value: 'Gamma' },
        originalValues: { default_value: '' },
      })
      .catch(() => {})
    await vi.advanceTimersByTimeAsync(1000)
    const second = store.dispatch('dashboardApplication/updateWidget', {
      widgetId: 13,
      values: { default_value: 'Delta' },
      originalValues: { default_value: 'Gamma' },
    })
    await vi.advanceTimersByTimeAsync(1000)
    serverWidgets.find(({ id }) => id === 13).default_value = 'Delta'
    finish[1].resolve({ data: {} })
    await second
    finish[0].reject(new Error('Save failed'))
    await first
    expect(store.state.dashboardApplication.widgetValues[13]).toBe('Gamma')
    expect(
      store.state.dashboardApplication.widgets.find(({ id }) => id === 13)
        .default_value
    ).toBe('Delta')
  })

  test.each([12, 13])(
    'releases a shared source only after both filter saves finish (first: %s)',
    async (firstId) => {
      const finish = {}
      store.$client.patch = vi.fn(
        (url) =>
          new Promise((resolve) => {
            finish[url] = () => resolve({ data: {} })
          })
      )
      store.$client.get = vi.fn(async () => ({
        data: [...store.state.dashboardApplication.widgets],
      }))
      await change(12, '')
      await vi.advanceTimersByTimeAsync(300)
      await settle()
      post.mockClear()
      const saving = {}
      for (const id of [12, 13]) {
        saving[id] = store.dispatch('dashboardApplication/updateWidget', {
          widgetId: id,
          values: { default_value: 'New' },
          originalValues: { default_value: id === 12 ? 'Alpha' : '' },
        })
      }
      await vi.advanceTimersByTimeAsync(1000)
      expect(post).not.toHaveBeenCalled()
      finish[`/dashboard/widgets/${firstId}/`]()
      await saving[firstId]
      await vi.advanceTimersByTimeAsync(300)
      const firstSource = firstId === 12 ? 1 : 2
      expect(requests.map(({ url }) => url)).toEqual([
        `/dashboard/data-sources/${firstSource}/dispatch/`,
      ])
      await settle()
      const secondId = firstId === 12 ? 13 : 12
      finish[`/dashboard/widgets/${secondId}/`]()
      await saving[secondId]
      await vi.advanceTimersByTimeAsync(300)
      const secondSource = firstId === 12 ? 2 : 1
      expect(requests.map(({ url }) => url).sort()).toEqual([
        `/dashboard/data-sources/${secondSource}/dispatch/`,
        '/dashboard/data-sources/3/dispatch/',
      ])
      await settle()
    }
  )

  test('does not resume pending refreshes after navigating away during a save', async () => {
    let finishSave
    store.$client.patch = vi.fn(
      () => new Promise((resolve) => (finishSave = resolve))
    )
    const saving = store.dispatch('dashboardApplication/updateWidget', {
      widgetId: 12,
      values: { default_value: 'New' },
      originalValues: { default_value: 'Alpha' },
    })
    await vi.advanceTimersByTimeAsync(1000)
    store.commit('dashboardApplication/RESET')
    finishSave({ data: {} })
    await saving
    await vi.advanceTimersByTimeAsync(1000)
    expect(post).not.toHaveBeenCalled()
  })

  test('keeps the shared dispatch payload valid while a filter changes value shape', async () => {
    await store.dispatch('dashboardApplication/forceUpdateWidget', {
      widgetId: 13,
      values: { mode: 'dropdown', multiple: false },
    })
    let finishSave
    store.$client.patch = vi.fn(
      () => new Promise((resolve) => (finishSave = resolve))
    )
    const saving = store.dispatch('dashboardApplication/updateWidget', {
      widgetId: 13,
      values: { multiple: true },
      originalValues: { multiple: false },
    })
    await change(12, 'Beta')
    await vi.advanceTimersByTimeAsync(1000)
    expect(post).not.toHaveBeenCalled()
    finishSave({ data: {} })
    await saving
    await vi.advanceTimersByTimeAsync(300)
    expect(requests.map(({ url }) => url)).toContain(
      '/dashboard/data-sources/1/dispatch/'
    )
    expect(requests[0].payload.widget_data[13]).toEqual([])
    await settle()
  })

  test.each([23, 20])(
    'does not wait for a title save on display widget %s',
    async (widgetId) => {
      let finishSave
      store.$client.patch = vi.fn(
        () => new Promise((resolve) => (finishSave = resolve))
      )
      const saving = store.dispatch('dashboardApplication/updateWidget', {
        widgetId,
        values: { title: 'Renamed' },
        originalValues: { title: '' },
      })
      await change(12, 'Beta')
      await vi.advanceTimersByTimeAsync(1000)
      expect(requests.map(({ url }) => url)).toEqual([
        '/dashboard/data-sources/1/dispatch/',
        '/dashboard/data-sources/3/dispatch/',
      ])
      await settle()
      finishSave({ data: {} })
      await saving
    }
  )

  test.each([false, true])(
    'only holds sources affected by a pending filter save (failure: %s)',
    async (failure) => {
      let finishSave
      store.$client.patch = vi.fn(
        () =>
          new Promise((resolve, reject) => {
            finishSave = failure
              ? () => reject(new Error('Save failed'))
              : () => resolve({ data: {} })
          })
      )
      const saving = store
        .dispatch('dashboardApplication/updateWidget', {
          widgetId: 13,
          values: { default_value: 'Other' },
          originalValues: { default_value: '' },
        })
        .catch(() => {})
      await change(12, 'Beta')
      await vi.advanceTimersByTimeAsync(1000)
      // Source 3 is shared by both filters; source 1 does not depend on filter 13.
      expect(requests.map(({ url }) => url)).toEqual([
        '/dashboard/data-sources/1/dispatch/',
      ])
      await settle()
      post.mockClear()
      await vi.advanceTimersByTimeAsync(1500)
      expect(post).not.toHaveBeenCalled()
      finishSave()
      await saving
      await vi.advanceTimersByTimeAsync(300)
      expect(requests.map(({ url }) => url).sort()).toEqual([
        '/dashboard/data-sources/2/dispatch/',
        '/dashboard/data-sources/3/dispatch/',
      ])
      expect(requests[0].payload.widget_data[13]).toBe(failure ? '' : 'Other')
      await settle()
    }
  )

  test('waits for removed targets as well as newly added targets', async () => {
    let finishSave
    store.$client.patch = vi.fn(
      () => new Promise((resolve) => (finishSave = resolve))
    )
    const saving = store.dispatch('dashboardApplication/updateWidget', {
      widgetId: 12,
      values: { target_filters: [{ target_widget_id: 21 }] },
      originalValues: { target_filters: widget.target_filters },
    })
    await vi.advanceTimersByTimeAsync(1000)
    expect(post).not.toHaveBeenCalled()
    finishSave({ data: {} })
    await saving
    await vi.advanceTimersByTimeAsync(300)
    expect(requests.map(({ url }) => url).sort()).toEqual([
      '/dashboard/data-sources/1/dispatch/',
      '/dashboard/data-sources/2/dispatch/',
      '/dashboard/data-sources/3/dispatch/',
    ])
    await settle()
  })

  test.each([false, true])(
    'waits for selection mode persistence before dispatching (failure: %s)',
    async (failure) => {
      await store.dispatch('dashboardApplication/forceUpdateWidget', {
        widgetId: 12,
        values: { mode: 'dropdown', multiple: false },
      })
      await change(12, 'Beta')
      await vi.advanceTimersByTimeAsync(300)
      await settle()
      post.mockClear()
      let finishSave
      store.$client.patch = vi.fn(
        () =>
          new Promise((resolve, reject) => {
            finishSave = failure
              ? () => reject(new Error('Save failed'))
              : () => resolve({ data: {} })
          })
      )
      const saving = store
        .dispatch('dashboardApplication/updateWidget', {
          widgetId: 12,
          values: { multiple: true, default_value: ['Alpha'] },
          originalValues: { multiple: false, default_value: 'Alpha' },
        })
        .catch(() => {})
      await vi.advanceTimersByTimeAsync(1000)
      expect(post).not.toHaveBeenCalled()
      finishSave()
      await saving
      await vi.advanceTimersByTimeAsync(300)
      expect(requests).toHaveLength(2)
      expect(requests[0].payload.widget_data[12]).toEqual(
        failure ? 'Beta' : ['Beta']
      )
      await settle()
    }
  )

  test.each([
    ['dropdown', false, 'Beta', 'dropdown', true, ['Beta']],
    ['dropdown', false, '', 'dropdown', true, []],
    ['dropdown', true, ['Beta', 'Gamma'], 'dropdown', false, 'Beta'],
    ['dropdown', true, [], 'dropdown', false, ''],
    ['dropdown', true, ['Beta', 'Gamma'], 'input', true, 'Beta'],
    ['input', true, 'Beta', 'dropdown', true, ['Beta']],
  ])(
    'preserves selection %j/%j/%j when switching to %j/%j',
    async (mode, multiple, selection, nextMode, nextMultiple, expected) => {
      await store.dispatch('dashboardApplication/forceUpdateWidget', {
        widgetId: 12,
        values: {
          mode,
          multiple,
          default_value:
            mode === 'dropdown' && multiple ? ['Alpha', 'Other'] : 'Alpha',
        },
      })
      await change(12, selection)
      await vi.advanceTimersByTimeAsync(300)
      await settle()
      await store.dispatch('dashboardApplication/forceUpdateWidget', {
        widgetId: 12,
        values: {
          mode: nextMode,
          multiple: nextMultiple,
          default_value:
            nextMode === 'dropdown' && nextMultiple ? ['Alpha'] : 'Alpha',
        },
      })
      expect(store.state.dashboardApplication.widgetValues[12]).toEqual(
        expected
      )
      await vi.advanceTimersByTimeAsync(300)
      expect(requests).toHaveLength(2)
      expect(requests[0].payload.widget_data[12]).toEqual(expected)
      await settle()
    }
  )

  test('preserves a selection when the default and mode change together', async () => {
    await change(12, 'Beta')
    await store.dispatch('dashboardApplication/forceUpdateWidget', {
      widgetId: 12,
      values: { mode: 'dropdown', multiple: true, default_value: ['Gamma'] },
    })
    expect(store.state.dashboardApplication.widgetValues[12]).toEqual(['Beta'])
  })

  test.each([
    [false, 'Beta', 'Gamma', 'Beta'],
    [false, 'Alpha', 'Gamma', 'Alpha'],
    [false, 'Beta', '', 'Beta'],
    [false, '', 'Gamma', 'Gamma'],
    [true, ['Beta', 'Other'], ['Gamma'], ['Beta', 'Other']],
    [true, ['Alpha'], ['Gamma'], ['Alpha']],
    [true, ['Beta'], [], ['Beta']],
    [true, [], ['Gamma'], ['Gamma']],
  ])(
    'only applies a changed default to an empty filter (multiple: %s, selection: %j, default: %j)',
    async (multiple, selection, defaultValue, expected) => {
      await store.dispatch('dashboardApplication/forceUpdateWidget', {
        widgetId: 12,
        values: { mode: 'dropdown', multiple },
      })
      await change(12, selection)
      await vi.advanceTimersByTimeAsync(300)
      await settle()
      post.mockClear()
      await store.dispatch('dashboardApplication/forceUpdateWidget', {
        widgetId: 12,
        values: { default_value: defaultValue },
      })
      expect(store.state.dashboardApplication.widgetValues[12]).toEqual(
        expected
      )
      await vi.advanceTimersByTimeAsync(300)
      if (selection.length) {
        expect(post).not.toHaveBeenCalled()
      } else {
        expect(requests).toHaveLength(2)
        expect(requests[0].payload.widget_data[12]).toEqual(expected)
      }
      await settle()
    }
  )

  test.each([
    [false, false],
    [true, false],
    [false, true],
    [true, true],
  ])(
    'rolls back an automatically applied default without overwriting later selections (changed: %s, coalesced: %s)',
    async (changed, coalesced) => {
      await store.dispatch('dashboardApplication/forceUpdateWidget', {
        widgetId: 13,
        values: { mode: 'dropdown', multiple: true, default_value: [] },
      })
      let failSave
      store.$client.patch = vi.fn(
        () =>
          new Promise((resolve, reject) => {
            failSave = () => reject(new Error('Save failed'))
          })
      )
      const saving = [
        store
          .dispatch('dashboardApplication/updateWidget', {
            widgetId: 13,
            values: { default_value: ['Gamma'] },
            originalValues: { default_value: [] },
          })
          .catch(() => {}),
      ]
      expect(store.state.dashboardApplication.widgetValues[13]).toEqual([
        'Gamma',
      ])
      if (coalesced) {
        if (changed) await change(13, ['Beta'])
        saving.push(
          store
            .dispatch('dashboardApplication/updateWidget', {
              widgetId: 13,
              values: { default_value: ['Delta'] },
              originalValues: { default_value: ['Gamma'] },
            })
            .catch(() => {})
        )
      }
      await vi.advanceTimersByTimeAsync(1000)
      if (changed && !coalesced) await change(13, ['Beta'])
      failSave()
      await Promise.all(saving)
      expect(store.state.dashboardApplication.widgetValues[13]).toEqual(
        changed ? ['Beta'] : []
      )
      expect(
        store.state.dashboardApplication.widgets.find(({ id }) => id === 13)
          .default_value
      ).toEqual([])
      await vi.advanceTimersByTimeAsync(300)
      await settle()
    }
  )

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

  test('preserves values on unrelated realtime updates and changed defaults', async () => {
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
    expect(store.state.dashboardApplication.widgetValues[12]).toBe('Typed')
    await vi.advanceTimersByTimeAsync(300)
    expect(post).not.toHaveBeenCalled()
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
