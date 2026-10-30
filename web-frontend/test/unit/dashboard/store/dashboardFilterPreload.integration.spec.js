import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardFilters from '@baserow/modules/dashboard/components/filter/DashboardFilters'

describe('dashboard filter option preloading', () => {
  let testApp, store, mock
  const filter = {
    id: 5,
    dashboard_id: 1,
    label: 'Team',
    type: 'text',
    operator: 'equal',
    mode: 'dropdown',
    multiple: true,
    formula_value: { formula: "get('table.1.*.field_20')", mode: 'simple' },
  }

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    mock = testApp.mock
    mock
      .onGet('/dashboard/1/widgets/')
      .reply(200, [
        { id: 2, dashboard_id: 1, data_source_id: 10, type: 'summary' },
      ])
    mock
      .onGet('/dashboard/1/filters/')
      .reply(200, [
        filter,
        { ...filter, id: 6, label: 'Country', multiple: false },
        { ...filter, id: 7, label: 'Search', mode: 'input' },
      ])
    mock
      .onGet('/dashboard/1/data-sources/')
      .reply(200, [{ id: 10, dashboard_id: 1 }])
    mock
      .onPost('/dashboard/data-sources/10/dispatch/')
      .reply(200, { result: 10 })
  })

  afterEach(() => testApp.afterEach())

  const openContext = () => testApp.body.get('.context:not(.visibility-hidden)')

  const load = () =>
    store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: 1,
      forEditing: false,
    })

  test('preloads dropdowns alongside widgets and opens cached choices without another request', async () => {
    const finish = {}
    for (const id of [5, 6]) {
      mock.onPost(`/dashboard/filters/${id}/options/`).reply(
        () =>
          new Promise((resolve) => {
            finish[id] = resolve
          })
      )
    }
    const initial = load()
    await vi.waitFor(() => {
      expect(finish[5]).toBeTypeOf('function')
      expect(finish[6]).toBeTypeOf('function')
      expect(
        mock.history.post.some(({ url }) => url.endsWith('/dispatch/'))
      ).toBe(true)
    })
    expect(store.getters['dashboardApplication/isLoading']).toBe(true)
    finish[5]([200, { results: ['Design'], next: null, available: [] }])
    await flushPromises()
    expect(store.getters['dashboardApplication/isLoading']).toBe(true)
    finish[6]([200, { results: [], next: null, available: [] }])
    await initial
    expect(store.getters['dashboardApplication/isLoading']).toBe(false)
    const wrapper = await testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: 1, workspace: { id: 1 } } },
    })
    await wrapper.findAll('.dropdown__selected')[0].trigger('click')
    await flushPromises()
    expect(openContext().get('.dashboard-filter__option-value').text()).toBe(
      'Design'
    )
    expect(openContext().find('[role="status"]').exists()).toBe(false)
    await openContext().get('form').trigger('keydown', { key: 'Escape' })
    await wrapper.findAll('.dropdown__selected')[1].trigger('click')
    await flushPromises()
    expect(openContext().text()).toContain('dashboardFilter.noOptions')
    expect(openContext().find('[role="status"]').exists()).toBe(false)
    expect(
      mock.history.post
        .filter(({ url }) => url.endsWith('/options/'))
        .map(({ url }) => url)
    ).toEqual([
      '/dashboard/filters/5/options/',
      '/dashboard/filters/6/options/',
    ])
  })

  test('shows the dashboard before slow widgets finish once choices are ready', async () => {
    mock.onPost(/\/dashboard\/filters\/[56]\/options\//).reply(200, {
      results: ['Design'],
      next: null,
      available: [],
    })
    let finishWidget
    mock.onPost('/dashboard/data-sources/10/dispatch/').reply(
      () =>
        new Promise((resolve) => {
          finishWidget = resolve
        })
    )
    const initial = load()
    await vi.waitFor(() => {
      expect(finishWidget).toBeTypeOf('function')
      expect(store.getters['dashboardApplication/isLoading']).toBe(false)
    })
    const wrapper = await testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: 1, workspace: { id: 1 } } },
    })
    await wrapper.findAll('.dropdown__selected')[0].trigger('click')
    await flushPromises()
    expect(openContext().get('.dashboard-filter__option-value').text()).toBe(
      'Design'
    )
    finishWidget([200, { result: 10 }])
    await initial
  })

  test('keeps the dashboard usable after an options failure and allows retry', async () => {
    testApp.dontFailOnErrorResponses()
    mock.onPost('/dashboard/filters/5/options/').reply(500)
    mock.onPost('/dashboard/filters/6/options/').reply(200, {
      results: ['France'],
      next: null,
      available: [],
    })
    await load()
    expect(store.getters['dashboardApplication/isLoading']).toBe(false)
    const wrapper = await testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: 1, workspace: { id: 1 } } },
    })
    await wrapper.findAll('.dropdown__selected')[0].trigger('click')
    await flushPromises()
    expect(
      mock.history.post.filter(
        ({ url }) => url === '/dashboard/filters/5/options/'
      )
    ).toHaveLength(1)
    expect(openContext().get('[role="status"]').text()).toContain(
      'dashboardFilter.optionsError'
    )
    mock.onPost('/dashboard/filters/5/options/').reply(200, {
      results: ['Design'],
      next: null,
      available: [],
    })
    await openContext().get('[role="status"] button').trigger('click')
    await flushPromises()
    expect(openContext().get('.dashboard-filter__option-value').text()).toBe(
      'Design'
    )
    expect(openContext().find('[role="status"]').exists()).toBe(false)
    await openContext().get('form').trigger('keydown', { key: 'Escape' })
    await wrapper.findAll('.dropdown__selected')[1].trigger('click')
    await flushPromises()
    expect(openContext().get('.dashboard-filter__option-value').text()).toBe(
      'France'
    )
    expect(
      mock.history.post.filter(
        ({ url }) => url === '/dashboard/filters/6/options/'
      )
    ).toHaveLength(1)
  })

  test('preloads the current filters when realtime changes them during the initial requests', async () => {
    const finish = {}
    for (const id of [5, 6]) {
      mock.onPost(`/dashboard/filters/${id}/options/`).reply(
        () =>
          new Promise((resolve) => {
            finish[id] = resolve
          })
      )
    }
    const initial = load()
    await vi.waitFor(() => expect(finish[6]).toBeTypeOf('function'))
    mock.onGet('/dashboard/1/filters/').reply(200, [
      {
        ...filter,
        formula_value: { formula: "get('table.1.*.field_21')", mode: 'simple' },
      },
      { ...filter, id: 8, label: 'New filter' },
    ])
    for (const id of [5, 8]) {
      mock.onPost(`/dashboard/filters/${id}/options/`).reply(200, {
        results: ['New'],
        next: null,
        available: [],
      })
    }
    await store.dispatch('dashboardApplication/handleFiltersUpdated')
    for (const id of [5, 6]) {
      finish[id]([200, { results: ['Old'], next: null, available: [] }])
    }
    await initial
    const requestsBeforeOpening = mock.history.post.length
    const wrapper = await testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: 1, workspace: { id: 1 } } },
    })
    for (const trigger of wrapper.findAll('.dropdown__selected')) {
      await trigger.trigger('click')
      await flushPromises()
      expect(openContext().get('.dashboard-filter__option-value').text()).toBe(
        'New'
      )
      expect(openContext().find('[role="status"]').exists()).toBe(false)
      await openContext().get('form').trigger('keydown', { key: 'Escape' })
    }
    expect(mock.history.post).toHaveLength(requestsBeforeOpening)
  })

  test('does not end another dashboard loading state when old options finish', async () => {
    const finish = {}
    for (const id of [5, 6, 8]) {
      mock.onPost(`/dashboard/filters/${id}/options/`).reply(
        () =>
          new Promise((resolve) => {
            finish[id] = resolve
          })
      )
    }
    const initial = load()
    await vi.waitFor(() => expect(finish[6]).toBeTypeOf('function'))
    mock.onGet('/dashboard/2/widgets/').reply(200, [])
    mock
      .onGet('/dashboard/2/filters/')
      .reply(200, [{ ...filter, id: 8, dashboard_id: 2, label: 'New team' }])
    mock.onGet('/dashboard/2/data-sources/').reply(200, [])
    const nextDashboard = store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: 2,
      forEditing: false,
    })
    await vi.waitFor(() => expect(finish[8]).toBeTypeOf('function'))
    for (const id of [5, 6]) {
      finish[id]([200, { results: ['Old'], next: null, available: [] }])
    }
    await initial
    expect(store.getters['dashboardApplication/isLoading']).toBe(true)
    finish[8]([200, { results: ['New'], next: null, available: [] }])
    await nextDashboard
    expect(store.getters['dashboardApplication/isLoading']).toBe(false)
    const wrapper = await testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: 2, workspace: { id: 1 } } },
    })
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    expect(openContext().get('.dashboard-filter__option-value').text()).toBe(
      'New'
    )
  })
})
