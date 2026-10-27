import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardFilters from '@baserow/modules/dashboard/components/filter/DashboardFilters'
import SummaryWidget from '@baserow/modules/dashboard/components/widget/SummaryWidget'
import { registerRealtimeEvents } from '@baserow/modules/dashboard/realtime'

// The API fixture is shared across app instances, just like the saved dashboard.
describe('shared dashboard filter selections', () => {
  let testApp, store, mock, filters
  const filter = {
    id: 5,
    dashboard_id: 1,
    label: 'Team',
    type: 'text',
    operator: 'equal',
    mode: 'dropdown',
    multiple: true,
    formula_value: { formula: 'Design, Sales', mode: 'simple' },
    values: [],
  }
  const makeSource = (dashboardId) => ({
    id: dashboardId,
    dashboard_id: dashboardId,
    filters: [
      {
        field: 1,
        type: 'equal',
        value: {
          formula: `get('dashboard_filter.${dashboardId + 4}')`,
          mode: 'simple',
        },
      },
    ],
  })

  function startApp(userId = 1) {
    testApp = new TestApp()
    testApp.authenticate({ id: userId })
    store = testApp.store
    mock = testApp.mock
    for (const dashboardId of [1, 2]) {
      mock
        .onGet(`/dashboard/${dashboardId}/filters/`)
        .reply(() => [
          200,
          filters.filter((item) => item.dashboard_id === dashboardId),
        ])
      mock.onGet(`/dashboard/${dashboardId}/widgets/`).reply(200, [
        {
          id: dashboardId,
          dashboard_id: dashboardId,
          data_source_id: dashboardId,
          type: 'summary',
        },
      ])
      mock
        .onGet(`/dashboard/${dashboardId}/data-sources/`)
        .reply(200, [makeSource(dashboardId)])
      mock
        .onPost(`/dashboard/data-sources/${dashboardId}/dispatch/`)
        .reply(200, {
          result: 10,
        })
    }
    for (const id of [5, 6]) {
      mock.onPatch(`/dashboard/filters/${id}/`).reply(({ data }) => {
        filters = filters.map((item) =>
          item.id === id ? { ...item, ...JSON.parse(data) } : item
        )
        return [200, filters.find((item) => item.id === id)]
      })
    }
    mock.onPost(/\/dashboard\/filters\/\d+\/options\/$/).reply(200, {
      results: ['Design', 'Sales'],
      next: null,
      available: ['Design', 'Sales'],
    })
  }

  async function load(dashboardId = 1) {
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId,
      forEditing: false,
    })
    return testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: dashboardId, workspace: { id: 1 } } },
    })
  }

  beforeEach(() => {
    filters = [{ ...filter }]
    startApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    sessionStorage.clear()
  })

  test('a saved selection is restored for another user in a fresh app', async () => {
    await load()
    await store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['Design'],
    })
    expect(mock.history.patch.map(({ data }) => JSON.parse(data))).toEqual([
      { values: ['Design'] },
    ])
    await testApp.afterEach()
    sessionStorage.clear()
    startApp(2)
    const wrapper = await load()
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
    expect(mock.history.patch).toHaveLength(0)
  })

  test.each([
    [{}, ['Design', 'Sales'], 'dashboardFilter.selections - 2'],
    [{ multiple: false }, ['Design'], 'Design'],
    [{ mode: 'input' }, ['Design'], 'Design'],
    [{ type: 'number', mode: 'input' }, ['42'], '42'],
    [{ operator: 'empty' }, ['true'], 'dashboardFilter.active'],
  ])(
    'loads saved %j values before fetching options',
    async (config, values, label) => {
      filters = [{ ...filter, ...config, values }]
      const wrapper = await load()
      expect(wrapper.get('.dashboard-filter__value').text()).toBe(label)
      expect(mock.history.patch).toHaveLength(0)
      expect(
        mock.history.post
          .filter(({ url }) => url.endsWith('/dispatch/'))
          .map(({ data }) => JSON.parse(data))
      ).toEqual([{}])
      expect(
        mock.history.post
          .filter(({ url }) => url.endsWith('/options/'))
          .map(({ data }) => JSON.parse(data))
      ).toEqual(
        config.mode === 'input' || config.operator === 'empty'
          ? []
          : [{ selected: values }]
      )
    }
  )

  test('ignores old private session selections instead of publishing them', async () => {
    sessionStorage.setItem(
      'baserow.dashboardFilters.1.1',
      JSON.stringify([{ ...filter, values: ['Sales'] }])
    )
    filters = [{ ...filter, values: ['Design'] }]
    const wrapper = await load()
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
    expect(mock.history.patch).toHaveLength(0)
  })

  test('clearing a shared selection persists for another user', async () => {
    filters = [{ ...filter, values: ['Design'] }]
    await load()
    await store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: [],
    })
    await testApp.afterEach()
    startApp(2)
    const wrapper = await load()
    expect(wrapper.get('.dashboard-filter__value').text()).toBe(
      'dashboardFilter.choose'
    )
  })

  test('keeps saved selections separate when navigating between dashboards', async () => {
    filters = [
      { ...filter, values: ['Design'] },
      { ...filter, id: 6, dashboard_id: 2, values: ['Sales'] },
    ]
    let wrapper = await load()
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
    wrapper.unmount()
    wrapper = await load(2)
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Sales')
    wrapper.unmount()
    wrapper = await load()
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
  })

  test('realtime updates replace the shared selection and refresh widgets without reloading choices', async () => {
    filters = [{ ...filter, values: ['Design'] }]
    const wrapper = await load()
    const handlers = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => {
        handlers[name] = handler
      },
    })
    mock.resetHistory()
    filters = [{ ...filter, values: ['Sales'] }]
    await handlers.dashboard_filters_updated({ store }, { dashboard_id: 1 })
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Sales')
    expect(mock.history.post.map(({ url }) => url)).toEqual([
      '/dashboard/data-sources/1/dispatch/',
    ])
    expect(mock.history.patch).toHaveLength(0)
  })

  test('refresh reconciles a missed shared selection change before refreshing options', async () => {
    const wrapper = await load()
    mock.resetHistory()
    filters = [{ ...filter, values: ['Sales'] }]
    await store.dispatch('dashboardApplication/refresh')
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Sales')
    const options = mock.history.post.find(({ url }) =>
      url.endsWith('/options/')
    )
    expect(JSON.parse(options.data)).toEqual({ selected: ['Sales'] })
  })

  test('a newly discovered widget source is loaded during selection reconciliation', async () => {
    await load()
    const widget = {
      id: 2,
      dashboard_id: 1,
      data_source_id: 2,
      type: 'summary',
    }
    await store.dispatch('dashboardApplication/handleNewWidgetCreated', widget)
    mock.onGet('/dashboard/1/data-sources/').reply(200, [
      makeSource(1),
      {
        id: 2,
        dashboard_id: 1,
        type: 'local_baserow_aggregate_rows',
        aggregation_type: 'count',
        context_data: { field: { id: 1, name: 'Name', type: 'text' } },
      },
    ])
    mock
      .onPost('/dashboard/data-sources/2/dispatch/')
      .reply(200, { result: 42 })
    mock.resetHistory()
    filters = [{ ...filter, values: ['Sales'] }]
    await store.dispatch('dashboardApplication/handleFiltersUpdated')
    const wrapper = await testApp.mount(SummaryWidget, { props: { widget } })
    expect(wrapper.text()).toBe('42')
    expect(mock.history.post.map(({ url }) => url)).toEqual([
      '/dashboard/data-sources/1/dispatch/',
      '/dashboard/data-sources/2/dispatch/',
    ])
  })

  test.each([
    ['realtime', 'selection'],
    ['realtime', 'order'],
    ['local', 'selection'],
    ['local', 'order'],
  ])(
    'a %s ordering update cannot swallow a saved selection when %s returns first',
    async (origin, first) => {
      const wrapper = await load()
      const handlers = {}
      registerRealtimeEvents({
        registerEvent: (name, handler) => {
          handlers[name] = handler
        },
      })
      const responses = []
      mock.onGet('/dashboard/1/filters/').reply(
        () =>
          new Promise((resolve) => {
            responses.push(resolve)
          })
      )
      mock.onPost('/dashboard/1/filters/order/').reply(204)
      mock.resetHistory()
      const selection = handlers.dashboard_filters_updated(
        { store },
        { dashboard_id: 1 }
      )
      await vi.waitFor(() => expect(responses).toHaveLength(1))
      filters = [{ ...filter, values: ['Sales'] }]
      const order =
        origin === 'realtime'
          ? handlers.dashboard_filters_updated(
              { store },
              { dashboard_id: 1, order_only: true }
            )
          : store.dispatch('dashboardApplication/orderFilters', [5])
      await vi.waitFor(() => expect(responses).toHaveLength(2))
      if (first === 'selection') {
        responses[0]([200, [{ ...filter, values: ['Design'] }]])
        await flushPromises()
        responses[1]([200, filters])
      } else {
        responses[1]([200, filters])
        await order
        responses[0]([200, [{ ...filter, values: ['Design'] }]])
      }
      await Promise.all([selection, order])
      expect(wrapper.get('.dashboard-filter__value').text()).toBe('Sales')
      expect(
        mock.history.post
          .filter(({ url }) => url.endsWith('/dispatch/'))
          .map(({ url }) => url)
      ).toEqual(['/dashboard/data-sources/1/dispatch/'])
      expect(responses).toHaveLength(2)
    }
  )

  test('overlapping selection and configuration updates reconcile without retrying each other', async () => {
    await load()
    const responses = []
    mock.onGet('/dashboard/1/filters/').reply(
      () =>
        new Promise((resolve) => {
          responses.push(resolve)
        })
    )
    mock.resetHistory()
    const configuration = store.dispatch(
      'dashboardApplication/handleFiltersUpdated'
    )
    await vi.waitFor(() => expect(responses).toHaveLength(1))
    const selection = store.dispatch(
      'dashboardApplication/handleFiltersUpdated'
    )
    await vi.waitFor(() => expect(responses).toHaveLength(2))
    const source = { ...makeSource(1), field_id: 42 }
    mock.onGet('/dashboard/1/data-sources/').reply(200, [source])
    responses[0]([200, [{ ...filter, label: 'Renamed' }]])
    await flushPromises()
    responses[1]([200, [{ ...filter, label: 'Renamed', values: ['Sales'] }]])
    await Promise.all([configuration, selection])
    expect(
      store.getters['dashboardApplication/getAppliedFilterValues'](5)
    ).toEqual(['Sales'])
    expect(
      store.getters['dashboardApplication/getDataSourceById'](1)
    ).toMatchObject(source)
    expect(
      mock.history.get.filter(({ url }) => url.endsWith('/filters/'))
    ).toHaveLength(2)
    expect(
      mock.history.get.filter(({ url }) => url.endsWith('/data-sources/'))
    ).toHaveLength(2)
    expect(
      mock.history.post.filter(({ url }) => url.endsWith('/dispatch/'))
    ).toHaveLength(1)
  })

  test('a failed save leaves the last shared selection and widget results intact', async () => {
    testApp.dontFailOnErrorResponses()
    filters = [{ ...filter, values: ['Design'] }]
    const wrapper = await load()
    mock.resetHistory()
    mock.onPatch('/dashboard/filters/5/').reply(500)
    await expect(
      store.dispatch('dashboardApplication/applyFilter', {
        filterId: 5,
        values: ['Sales'],
      })
    ).rejects.toBeInstanceOf(Error)
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
    expect(mock.history.post).toHaveLength(0)
  })

  test('a delayed save response cannot overwrite a more recent shared selection', async () => {
    await load()
    let finishSave
    mock.onPatch('/dashboard/filters/5/').reply(
      () =>
        new Promise((resolve) => {
          finishSave = resolve
        })
    )
    const saving = store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['Design'],
    })
    await vi.waitFor(() => expect(finishSave).toBeTypeOf('function'))
    filters = [{ ...filter, values: ['Sales'] }]
    await store.dispatch('dashboardApplication/handleFiltersUpdated')
    finishSave([200, { ...filter, values: ['Design'] }])
    await saving
    expect(
      store.getters['dashboardApplication/getAppliedFilterValues'](5)
    ).toEqual(['Sales'])
  })

  test('a delayed save does not change the dashboard navigated to in the meantime', async () => {
    filters.push({ ...filter, id: 6, dashboard_id: 2, values: ['Sales'] })
    const previous = await load()
    let finishSave
    mock.onPatch('/dashboard/filters/5/').reply(
      () =>
        new Promise((resolve) => {
          finishSave = resolve
        })
    )
    const saving = store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['Design'],
    })
    await vi.waitFor(() => expect(finishSave).toBeTypeOf('function'))
    previous.unmount()
    const current = await load(2)
    mock.resetHistory()
    finishSave([200, { ...filter, values: ['Design'] }])
    await saving
    expect(current.get('.dashboard-filter__value').text()).toBe('Sales')
    expect(mock.history.get).toHaveLength(0)
    expect(mock.history.post).toHaveLength(0)
  })

  test.each(['initial', 'realtime'])(
    'the latest shared selection wins when %s loading finishes first',
    async (first) => {
      let finishInitial, finishRealtime
      let count = 0
      mock.onGet('/dashboard/1/filters/').reply(() => {
        count += 1
        if (count > 2) return [200, filters]
        return new Promise((resolve) => {
          if (count === 1) finishInitial = resolve
          else finishRealtime = resolve
        })
      })
      const loading = load()
      await vi.waitFor(() => expect(finishInitial).toBeTypeOf('function'))
      const realtime = store.dispatch(
        'dashboardApplication/handleFiltersUpdated'
      )
      await vi.waitFor(() => expect(finishRealtime).toBeTypeOf('function'))
      filters = [{ ...filter, values: ['Sales'] }]
      if (first === 'initial') {
        finishInitial([200, [{ ...filter, values: ['Design'] }]])
        await flushPromises()
        finishRealtime([200, filters])
      } else {
        finishRealtime([200, filters])
        await realtime
        finishInitial([200, [{ ...filter, values: ['Design'] }]])
      }
      const wrapper = await loading
      await realtime
      expect(wrapper.get('.dashboard-filter__value').text()).toBe('Sales')
      expect(mock.history.patch).toHaveLength(0)
    }
  )
})
