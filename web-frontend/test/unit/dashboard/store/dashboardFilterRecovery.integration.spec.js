import { TestApp } from '@baserow/test/helpers/testApp'

describe('dashboard filter creation recovery', () => {
  let app, store, mock, filters
  const filter = {
    id: 5,
    dashboard_id: 1,
    type: 'text',
    mode: 'input',
    values: [],
  }

  beforeEach(() => {
    app = new TestApp()
    app.dontFailOnErrorResponses()
    store = app.store
    mock = app.mock
    filters = []
    store.commit('dashboardApplication/SET_DASHBOARD_ID', 1)
    mock.onPost('/dashboard/1/filters/').reply(() => {
      filters.push(filter)
      return [201, filter]
    })
    mock.onGet('/dashboard/1/filters/').reply(() => [200, filters])
    mock.onGet('/dashboard/1/data-sources/').reply(200, [])
  })
  afterEach(() => app.afterEach())

  test.each(['filters', 'data-sources'])(
    'retries a failed %s refresh without repeating creation',
    async (collection) => {
      let reads = 0
      mock.onGet(`/dashboard/1/${collection}/`).reply(() => {
        reads += 1
        return reads === 1
          ? [500]
          : [200, collection === 'filters' ? filters : []]
      })
      await expect(
        store.dispatch('dashboardApplication/createFilter', { label: 'New' })
      ).resolves.toEqual(filter)
      expect(mock.history.post).toHaveLength(1)
      expect(store.getters['dashboardApplication/getSelectedFilter']).toEqual(
        filter
      )
      expect(store.state.toast.items).toEqual([])
      expect(reads).toBe(2)
    }
  )

  test('reports an already-created filter when both read attempts fail and Refresh recovers it', async () => {
    mock.onGet('/dashboard/1/filters/').reply(500)
    await expect(
      store.dispatch('dashboardApplication/createFilter', { label: 'New' })
    ).resolves.toEqual(filter)
    expect(filters).toEqual([filter])
    expect(mock.history.post).toHaveLength(1)
    expect(mock.history.get).toHaveLength(2)
    expect(store.state.toast.items).toMatchObject([
      {
        type: 'warning',
        title: 'dashboardFilter.createdRefreshFailedTitle',
        message: 'dashboardFilter.createdRefreshFailedMessage',
      },
    ])
    mock.onGet('/dashboard/1/filters/').reply(() => [200, filters])
    await store.dispatch('dashboardApplication/refresh')
    expect(store.getters['dashboardApplication/getSelectedFilter']).toEqual(
      filter
    )
    expect(mock.history.post).toHaveLength(1)
  })

  test('a delayed creation response cannot replace newer configuration', async () => {
    let finishCreate
    mock.onPost('/dashboard/1/filters/').reply(
      () =>
        new Promise((resolve) => {
          finishCreate = resolve
        })
    )
    const creation = store.dispatch('dashboardApplication/createFilter', {
      label: 'New',
    })
    await vi.waitFor(() => expect(finishCreate).toBeTypeOf('function'))
    filters = [{ ...filter, label: 'Renamed elsewhere' }]
    await store.dispatch('dashboardApplication/fetchFilters')
    mock.onGet('/dashboard/1/filters/').reply(500)
    finishCreate([201, { ...filter, label: 'New' }])
    await creation
    expect(store.getters['dashboardApplication/getFilters']).toEqual(filters)
  })

  test('Refresh retries failed source reconciliation before dispatching newly discovered sources', async () => {
    mock.onGet('/dashboard/1/data-sources/').reply(500)
    await expect(
      store.dispatch('dashboardApplication/createFilter', { label: 'New' })
    ).resolves.toEqual(filter)
    expect(mock.history.post).toHaveLength(1)
    expect(store.state.toast.items).toMatchObject([{ type: 'warning' }])
    mock
      .onGet('/dashboard/1/data-sources/')
      .reply(200, [{ id: 12, dashboard_id: 1 }])
    mock
      .onPost('/dashboard/data-sources/12/dispatch/')
      .reply(200, { result: 42 })
    await store.dispatch('dashboardApplication/refresh')
    expect(
      store.getters['dashboardApplication/getDataForDataSource'](12)
    ).toEqual({ result: 42 })
    expect(filters).toEqual([filter])
    expect(mock.history.post.map(({ url }) => url)).toEqual([
      '/dashboard/1/filters/',
      '/dashboard/data-sources/12/dispatch/',
    ])
  })

  test('a failed refresh after navigation does not retry or report against the new dashboard', async () => {
    let finishRefresh
    mock.onGet('/dashboard/1/filters/').reply(
      () =>
        new Promise((resolve) => {
          finishRefresh = resolve
        })
    )
    const creation = store.dispatch('dashboardApplication/createFilter', {
      label: 'New',
    })
    await vi.waitFor(() => expect(finishRefresh).toBeTypeOf('function'))
    await store.dispatch('dashboardApplication/reset')
    store.commit('dashboardApplication/SET_DASHBOARD_ID', 2)
    finishRefresh([500])
    await expect(creation).resolves.toEqual(filter)
    expect(mock.history.get).toHaveLength(1)
    expect(store.state.toast.items).toEqual([])
    expect(store.getters['dashboardApplication/getFilters']).toEqual([])
  })
})
