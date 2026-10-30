import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'
import { registerRealtimeEvents } from '@baserow/modules/dashboard/realtime'

describe('dashboard filter dependent source refresh', () => {
  let testApp, store, mock, filters, sources, handlers
  const condition = (id) => ({
    field: 1,
    type: 'equal',
    value: { formula: `get('dashboard_filter.${id}')`, mode: 'simple' },
  })
  const source = (id, conditions = []) => ({
    id,
    dashboard_id: 1,
    type: 'local_baserow_aggregate_rows',
    aggregation_type: 'count',
    filters: conditions,
    context_data: { field: { type: 'text' } },
  })
  const dispatchUrls = () => mock.history.post.map(({ url }) => url)
  const apply = (filterId, values) =>
    store.dispatch('dashboardApplication/applyFilter', { filterId, values })
  const remote = () =>
    handlers.dashboard_filters_updated({ store }, { dashboard_id: 1 })
  const load = () =>
    store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: 1,
      forEditing: false,
    })

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    mock = testApp.mock
    filters = [5, 6].map((id) => ({
      id,
      dashboard_id: 1,
      type: 'text',
      operator: 'equal',
      mode: 'input',
      multiple: false,
      values: [],
    }))
    sources = [
      source(10, [condition(5)]),
      source(20, [condition(6)]),
      source(30),
    ]
    handlers = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => {
        handlers[name] = handler
      },
    })
    mock.onGet('/dashboard/1/widgets/').reply(
      200,
      sources.map(({ id }) => ({
        id,
        dashboard_id: 1,
        type: 'summary',
        data_source_id: id,
      }))
    )
    mock.onGet('/dashboard/1/filters/').reply(() => [200, filters])
    mock.onGet('/dashboard/1/data-sources/').reply(() => [200, sources])
    for (const filterId of [5, 6]) {
      mock.onPatch(`/dashboard/filters/${filterId}/`).reply(({ data }) => {
        const filter = filters.find(({ id }) => id === filterId)
        Object.assign(filter, JSON.parse(data))
        return [200, filter]
      })
    }
    for (const id of [10, 20, 30, 40]) {
      mock
        .onPost(`/dashboard/data-sources/${id}/dispatch/`)
        .reply(200, { result: 42 })
    }
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('only linked widgets reload and unrelated summaries retain their value while dispatch is pending', async () => {
    await load()
    const widgets = store.getters['dashboardApplication/getWidgets']
    const wrappers = await Promise.all(
      widgets.map((widget) =>
        testApp.mount(DashboardWidget, {
          props: { widget, dashboard: { id: 1, workspace: { id: 1 } } },
        })
      )
    )
    let finish
    mock.onPost('/dashboard/data-sources/10/dispatch/').reply(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    mock.resetHistory()
    const saving = apply(5, ['France'])
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'))
    expect(dispatchUrls()).toEqual(['/dashboard/data-sources/10/dispatch/'])
    expect(wrappers[0].classes()).toContain('skeleton-loading')
    for (const wrapper of wrappers.slice(1)) {
      expect(wrapper.classes()).not.toContain('skeleton-loading')
      expect(wrapper.get('.dashboard-summary-widget__summary').text()).toBe(
        '42'
      )
    }
    finish([200, { result: 12 }])
    await saving
    expect(wrappers[0].get('.dashboard-summary-widget__summary').text()).toBe(
      '12'
    )
    mock
      .onPost('/dashboard/data-sources/10/dispatch/')
      .reply(200, { result: 42 })
    mock.resetHistory()
    await apply(5, [])
    expect(dispatchUrls()).toEqual(['/dashboard/data-sources/10/dispatch/'])
  })

  test('independent saves and a realtime echo do not restart another pending source', async () => {
    await load()
    let finish
    mock.onPost('/dashboard/data-sources/10/dispatch/').reply(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    mock.resetHistory()
    const first = apply(5, ['France'])
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'))
    await apply(6, ['Design'])
    await remote()
    expect(dispatchUrls()).toEqual([
      '/dashboard/data-sources/10/dispatch/',
      '/dashboard/data-sources/20/dispatch/',
    ])
    finish([200, { result: 12 }])
    await first
  })

  test('remote selections reload their dependent sources and repeated events reuse the result', async () => {
    await load()
    mock.resetHistory()
    filters[1].values = ['Sales']
    await remote()
    await remote()
    expect(dispatchUrls()).toEqual(['/dashboard/data-sources/20/dispatch/'])
  })

  test('a delayed PATCH response after its realtime event does not reload the source twice', async () => {
    await load()
    let finish
    mock.onPatch('/dashboard/filters/5/').reply(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    mock.resetHistory()
    const saving = apply(5, ['France'])
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'))
    filters[0].values = ['France']
    await remote()
    finish([200, filters[0]])
    await saving
    expect(dispatchUrls()).toEqual(['/dashboard/data-sources/10/dispatch/'])
  })

  test('reconciliation loads newly discovered sources even without a filter dependency', async () => {
    await load()
    sources.push(source(40))
    filters[0].values = ['France']
    mock.resetHistory()
    await remote()
    expect(dispatchUrls()).toEqual([
      '/dashboard/data-sources/10/dispatch/',
      '/dashboard/data-sources/40/dispatch/',
    ])
  })

  test('configuration changes and removed source conditions still refresh the affected source', async () => {
    await load()
    mock.resetHistory()
    await store.dispatch('dashboardApplication/updateFilter', {
      filterId: 5,
      values: { operator: 'contains' },
    })
    expect(dispatchUrls()).toEqual(['/dashboard/data-sources/10/dispatch/'])
    filters = filters.filter(({ id }) => id !== 5)
    sources[0].filters = []
    mock.resetHistory()
    await remote()
    expect(dispatchUrls()).toEqual(['/dashboard/data-sources/10/dispatch/'])
  })

  test.each([{ type: 'number' }, { mode: 'dropdown' }])(
    'changing %j resets the active selection and reloads only its widget without fetching sources',
    async (changes) => {
      filters[0].values = ['France']
      await load()
      const wrappers = await Promise.all(
        store.getters['dashboardApplication/getWidgets'].map((widget) =>
          testApp.mount(DashboardWidget, {
            props: { widget, dashboard: { id: 1, workspace: { id: 1 } } },
          })
        )
      )
      mock.onPatch('/dashboard/filters/5/').reply(({ data }) => {
        filters[0] = { ...filters[0], ...JSON.parse(data), values: [] }
        return [200, structuredClone(filters[0])]
      })
      mock
        .onPost('/dashboard/data-sources/10/dispatch/')
        .reply(200, { result: 12 })
      mock.resetHistory()

      await store.dispatch('dashboardApplication/updateFilter', {
        filterId: 5,
        values: changes,
      })

      expect(
        store.getters['dashboardApplication/getAppliedFilterValues'](5)
      ).toEqual([])
      expect(dispatchUrls()).toEqual(['/dashboard/data-sources/10/dispatch/'])
      expect(
        wrappers.map((wrapper) =>
          wrapper.get('.dashboard-summary-widget__summary').text()
        )
      ).toEqual(['12', '42', '42'])
      expect(
        mock.history.get.filter(({ url }) => url.endsWith('/data-sources/'))
      ).toHaveLength(0)
    }
  )

  test.each([200, 500, 'superseded'])(
    'a mode change shares pending restored source definitions and their %s outcome',
    async (status) => {
      if (status !== 200) testApp.dontFailOnErrorResponses()
      const restoredFilter = { ...filters[0], values: ['France'] }
      filters = [{ ...filters[1], values: ['Sales'] }]
      sources[0] = source(10)
      await load()
      const widget = store.getters['dashboardApplication/getWidgetById'](10)
      const wrapper = await testApp.mount(DashboardWidget, {
        props: { widget, dashboard: { id: 1, workspace: { id: 1 } } },
      })

      filters = [restoredFilter, ...filters]
      sources[0] = source(10, [condition(5)])
      mock
        .onGet('/dashboard/1/filters/')
        .reply(() => [200, structuredClone(filters)])
      mock.onPatch('/dashboard/filters/6/').reply(({ data }) => {
        filters[1] = { ...filters[1], ...JSON.parse(data), values: [] }
        return [200, structuredClone(filters[1])]
      })
      mock
        .onPost('/dashboard/data-sources/10/dispatch/')
        .reply(200, { result: 12 })
      mock
        .onPost('/dashboard/data-sources/20/dispatch/')
        .reply(200, { result: 24 })
      const reads = []
      mock.onGet('/dashboard/1/data-sources/').reply(() => {
        const data = structuredClone(sources)
        return new Promise((resolve) => reads.push({ data, resolve }))
      })
      mock.resetHistory()
      const restoring = remote().then(
        () => ({ status: 'fulfilled' }),
        (error) => ({ status: 'rejected', error })
      )
      await vi.waitFor(() => expect(reads).toHaveLength(1))
      let saveSettled = false
      const changes = { filterId: 6, values: { mode: 'dropdown' } }
      const saving = store
        .dispatch('dashboardApplication/updateFilter', changes)
        .then(
          () => {
            saveSettled = true
            return { status: 'fulfilled' }
          },
          (error) => {
            saveSettled = true
            return { status: 'rejected', error }
          }
        )
      await flushPromises()
      const settledBeforeSources = saveSettled
      const dispatchesBeforeSources = dispatchUrls()
      const pending = [restoring, saving]
      if (status === 'superseded') {
        let finishFilters
        mock.onGet('/dashboard/1/filters/').reply(
          () =>
            new Promise((resolve) => {
              finishFilters = resolve
            })
        )
        pending.push(
          remote().then(
            () => ({ status: 'fulfilled' }),
            (error) => ({ status: 'rejected', error })
          )
        )
        await vi.waitFor(() => expect(finishFilters).toBeTypeOf('function'))
        // The newer reconciliation is still reading filters, so its source
        // request cannot supersede the old failed source request yet.
        reads[0].resolve([500])
        await flushPromises()
        expect.soft(saveSettled).toBe(false)
        expect.soft(dispatchUrls()).toEqual([])
        expect.soft(reads).toHaveLength(1)
        finishFilters([200, structuredClone(filters)])
        await vi.waitFor(() => expect(reads).toHaveLength(2))
        reads[1].resolve([200, reads[1].data])
      } else {
        reads.forEach(({ data, resolve }) =>
          resolve([status, status === 200 ? data : {}])
        )
      }
      const outcomes = await Promise.all(pending)

      expect(settledBeforeSources).toBe(false)
      expect(dispatchesBeforeSources).toEqual([])
      expect(reads).toHaveLength(status === 'superseded' ? 2 : 1)
      if (status === 500) {
        expect(outcomes.map(({ status }) => status)).toEqual([
          'rejected',
          'rejected',
        ])
        expect(outcomes.map(({ error }) => error.response.status)).toEqual([
          500, 500,
        ])
        expect(dispatchUrls()).toEqual([])
        expect(wrapper.get('.dashboard-summary-widget__summary').text()).toBe(
          '42'
        )
        expect(
          store.getters['dashboardApplication/getDataSourceById'](10).filters
        ).toEqual([])

        mock
          .onGet('/dashboard/1/data-sources/')
          .reply(() => [200, structuredClone(sources)])
        mock.resetHistory()
        await store.dispatch('dashboardApplication/updateFilter', changes)
        expect(
          mock.history.get.filter(({ url }) => url.endsWith('/data-sources/'))
        ).toHaveLength(1)
      } else {
        expect(outcomes.map(({ status }) => status)).toEqual(
          pending.map(() => 'fulfilled')
        )
      }
      expect(dispatchUrls()).toEqual([
        '/dashboard/data-sources/10/dispatch/',
        '/dashboard/data-sources/20/dispatch/',
      ])
      expect(wrapper.get('.dashboard-summary-widget__summary').text()).toBe(
        '12'
      )
      expect(
        store.getters['dashboardApplication/getDataForDataSource'](20)
      ).toEqual({ result: 24 })
      expect(
        store.getters['dashboardApplication/getDataSourceById'](10).filters
      ).toEqual([condition(5)])
    }
  )

  test.each([200, 500])(
    'restored filters await the current source definitions when the winning read returns %s',
    async (status) => {
      if (status === 500) testApp.dontFailOnErrorResponses()
      const restoredFilter = { ...filters[0], values: ['France'] }
      filters = filters.slice(1)
      sources[0] = source(10)
      await load()
      const widget = store.getters['dashboardApplication/getWidgetById'](10)
      const wrapper = await testApp.mount(DashboardWidget, {
        props: { widget, dashboard: { id: 1, workspace: { id: 1 } } },
      })

      // Restoring a filter also restores its removed source conditions, without
      // emitting a separate data_source_updated event.
      filters = [restoredFilter, ...filters]
      sources[0] = source(10, [condition(5)])
      mock
        .onPost('/dashboard/data-sources/10/dispatch/')
        .reply(200, { result: 12 })
      const reads = []
      mock.onGet('/dashboard/1/data-sources/').reply(() => {
        const data = structuredClone(sources)
        return new Promise((resolve) => reads.push({ data, resolve }))
      })
      mock.resetHistory()
      let firstSettled = false
      const first = remote().then(
        () => {
          firstSettled = true
          return { status: 'fulfilled' }
        },
        (error) => {
          firstSettled = true
          return { status: 'rejected', error }
        }
      )
      await vi.waitFor(() => expect(reads).toHaveLength(1))
      const second = handlers
        .dashboard_filters_updated(
          { store },
          { dashboard_id: 1, order_only: true }
        )
        .then(
          () => ({ status: 'fulfilled' }),
          (error) => ({ status: 'rejected', error })
        )
      await vi.waitFor(() => expect(reads).toHaveLength(2))
      reads[0].resolve([200, reads[0].data])
      await flushPromises()
      const settledBeforeWinner = firstSettled
      reads[1].resolve([status, status === 200 ? reads[1].data : {}])
      const outcomes = await Promise.all([first, second])

      expect(settledBeforeWinner).toBe(false)
      if (status === 200) {
        expect(outcomes.map(({ status }) => status)).toEqual([
          'fulfilled',
          'fulfilled',
        ])
        expect(dispatchUrls()).toEqual(['/dashboard/data-sources/10/dispatch/'])
        expect(wrapper.get('.dashboard-summary-widget__summary').text()).toBe(
          '12'
        )
      } else {
        expect(outcomes.map(({ status }) => status)).toEqual([
          'rejected',
          'rejected',
        ])
        expect(outcomes.map(({ error }) => error.response.status)).toEqual([
          500, 500,
        ])
        expect(dispatchUrls()).toEqual([])
        expect(wrapper.get('.dashboard-summary-widget__summary').text()).toBe(
          '42'
        )
        expect(
          store.getters['dashboardApplication/getDataSourceById'](10).filters
        ).toEqual([])
      }
    }
  )

  test('restored filters reread source definitions invalidated by a failed source update', async () => {
    testApp.dontFailOnErrorResponses()
    const restoredFilter = { ...filters[0], values: ['France'] }
    filters = filters.slice(1)
    sources[0] = source(10)
    await load()
    const widget = store.getters['dashboardApplication/getWidgetById'](10)
    const wrapper = await testApp.mount(DashboardWidget, {
      props: { widget, dashboard: { id: 1, workspace: { id: 1 } } },
    })

    filters = [restoredFilter, ...filters]
    sources[0] = source(10, [condition(5)])
    mock
      .onPost('/dashboard/data-sources/10/dispatch/')
      .reply(200, { result: 12 })
    mock.onPatch('/dashboard/data-sources/10/').reply(500)
    let finishSourceRead
    mock.onGet('/dashboard/1/data-sources/').reply(() => {
      const data = structuredClone(sources)
      if (finishSourceRead) return [200, data]
      return new Promise((resolve) => {
        finishSourceRead = () => resolve([200, data])
      })
    })
    mock.resetHistory()
    const restoring = remote()
    await vi.waitFor(() => expect(finishSourceRead).toBeTypeOf('function'))
    await expect(
      store.dispatch('dashboardApplication/updateDataSource', {
        dataSourceId: 10,
        values: { aggregation_type: 'sum' },
      })
    ).rejects.toMatchObject({ response: { status: 500 } })
    finishSourceRead()
    await restoring

    expect(wrapper.get('.dashboard-summary-widget__summary').text()).toBe('12')
    expect(dispatchUrls()).toEqual(['/dashboard/data-sources/10/dispatch/'])
    expect(
      mock.history.get.filter(({ url }) => url === '/dashboard/1/data-sources/')
    ).toHaveLength(2)
    expect(
      store.getters['dashboardApplication/getDataSourceById'](10).filters
    ).toEqual([condition(5)])
  })

  test('labels, ordering and source schema metadata do not reload results', async () => {
    await load()
    filters[0].label = 'Renamed'
    filters.reverse()
    sources[0].name = 'Renamed source'
    sources[0].context_data = { field: { name: 'New name', type: 'text' } }
    sources[0].table_schema = { properties: {} }
    mock.resetHistory()
    await remote()
    expect(dispatchUrls()).toEqual([])
  })

  test('local and realtime ordering reconciles sources without reloading unchanged widgets', async () => {
    await load()
    mock.onPost('/dashboard/1/filters/order/').reply(204)
    mock.resetHistory()
    filters.reverse()
    await store.dispatch('dashboardApplication/orderFilters', [6, 5])
    await handlers.dashboard_filters_updated(
      { store },
      { dashboard_id: 1, order_only: true }
    )
    expect(dispatchUrls().filter((url) => url.endsWith('/dispatch/'))).toEqual(
      []
    )
    expect(
      store.getters['dashboardApplication/getFilters'].map(({ id }) => id)
    ).toEqual([6, 5])
  })

  test('explicit Refresh reloads all sources and can retry an unchanged failed source', async () => {
    await load()
    testApp.dontFailOnErrorResponses()
    mock.onPost('/dashboard/data-sources/10/dispatch/').reply(500)
    await apply(5, ['France'])
    expect(
      store.getters['dashboardApplication/getDataForDataSource'](10)
    ).toEqual({ _error: true })
    mock
      .onPost('/dashboard/data-sources/10/dispatch/')
      .reply(200, { result: 42 })
    mock.resetHistory()
    await store.dispatch('dashboardApplication/refresh')
    expect(dispatchUrls()).toEqual([
      '/dashboard/data-sources/10/dispatch/',
      '/dashboard/data-sources/20/dispatch/',
      '/dashboard/data-sources/30/dispatch/',
    ])
    expect(
      store.getters['dashboardApplication/getDataForDataSource'](10)
    ).toEqual({ result: 42 })
  })

  test('a removed and restored source does not reuse its previous dispatch inputs', async () => {
    await load()
    const removed = sources.shift()
    await remote()
    sources.unshift(removed)
    mock.resetHistory()
    await remote()
    expect(dispatchUrls()).toEqual(['/dashboard/data-sources/10/dispatch/'])
  })
})
