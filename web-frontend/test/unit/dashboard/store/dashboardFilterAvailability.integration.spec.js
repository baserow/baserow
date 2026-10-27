import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardFilters from '@baserow/modules/dashboard/components/filter/DashboardFilters'
import { flushPromises } from '@vue/test-utils'

describe('shared selection option availability', () => {
  let app, store, mock, filters
  const filter = {
    id: 5,
    dashboard_id: 1,
    label: 'Team',
    type: 'text',
    operator: 'equal',
    mode: 'dropdown',
    multiple: true,
    formula_value: { formula: 'Design,Sales', mode: 'simple' },
    values: ['Design'],
  }
  beforeEach(async () => {
    app = new TestApp()
    store = app.store
    mock = app.mock
    filters = [filter]
    mock.onGet('/dashboard/1/widgets/').reply(200, [])
    mock.onGet('/dashboard/1/filters/').reply(() => [200, filters])
    mock.onGet('/dashboard/1/data-sources/').reply(200, [])
    mock.onPost('/dashboard/filters/5/options/').reply(200, {
      results: ['Design'],
      next: null,
      snapshot: 'snapshot-a',
      available: ['Design'],
    })
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: 1,
      forEditing: false,
    })
    mock.resetHistory()
  })
  afterEach(() => app.afterEach())
  const options = () =>
    store.getters['dashboardApplication/getFilterOptions'](5)
  const select = async (values) => {
    filters = [{ ...filter, values }]
    await store.dispatch('dashboardApplication/handleFiltersUpdated')
  }

  test('checks a new shared selection against a completed snapshot and shows missing values', async () => {
    const wrapper = await app.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: 1, workspace: { id: 1 } } },
    })
    mock.onPost('/dashboard/filters/5/options/').reply(200, {
      results: ['Design'],
      next: 'unused-page',
      snapshot: 'snapshot-a',
      available: [],
    })
    await select(['Gone'])
    await flushPromises()
    expect(mock.history.post.map(({ data }) => JSON.parse(data))).toEqual([
      { after: 'snapshot-a', limit: 1, selected: ['Gone'] },
    ])
    expect(options()).toMatchObject({
      results: ['Design'],
      next: null,
      unavailable: ['Gone'],
      loading: false,
      loaded: true,
    })
    expect(wrapper.find('.dashboard-filter__info').exists()).toBe(true)
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    expect(app.body.find('.dashboard-filter__unavailable').exists()).toBe(true)
    expect(mock.history.post).toHaveLength(1)
  })

  test('does not infer absence from a partially loaded page or reload known choices', async () => {
    store.commit('dashboardApplication/SET_FILTER_OPTIONS', {
      filterId: 5,
      values: { next: 'page-2' },
    })
    mock.onPost('/dashboard/filters/5/options/').reply(200, {
      results: ['Design'],
      next: 'ignored',
      snapshot: 'snapshot-a',
      available: ['Off-page'],
    })
    await select(['Off-page'])
    expect(options()).toMatchObject({
      results: ['Design'],
      next: 'page-2',
      unavailable: [],
    })
    await select(['Design'])
    await select(['Off-page'])
    expect(mock.history.post).toHaveLength(1)
  })

  test('merges overlapping checks for the same snapshot even when responses arrive backwards', async () => {
    const responses = []
    mock
      .onPost('/dashboard/filters/5/options/')
      .reply(() => new Promise((resolve) => responses.push(resolve)))
    const first = select(['Gone'])
    await vi.waitFor(() => expect(responses).toHaveLength(1))
    const second = select(['Off-page'])
    await vi.waitFor(() => expect(responses).toHaveLength(2))
    responses[1]([200, { available: ['Off-page'] }])
    await second
    responses[0]([200, { available: [] }])
    await first
    expect(options()).toMatchObject({
      unavailable: ['Gone'],
      results: ['Design'],
    })
    await select(['Off-page', 'Gone'])
    expect(mock.history.post).toHaveLength(2)
  })

  test('ignores a membership response after a new snapshot replaces its choices', async () => {
    let finishCheck
    mock.onPost('/dashboard/filters/5/options/').reply(
      () =>
        new Promise((resolve) => {
          finishCheck = resolve
        })
    )
    const selecting = select(['Gone'])
    await vi.waitFor(() => expect(finishCheck).toBeTypeOf('function'))
    mock.onPost('/dashboard/filters/5/options/').reply(200, {
      results: ['Gone'],
      next: null,
      snapshot: 'snapshot-b',
      available: ['Gone'],
    })
    await store.dispatch('dashboardApplication/fetchFilterOptions', {
      filterId: 5,
    })
    finishCheck([200, { available: [] }])
    await selecting
    expect(options()).toMatchObject({
      snapshot: 'snapshot-b',
      results: ['Gone'],
      unavailable: [],
    })
  })

  test.each(['automatic', 'cached picker'])(
    'a failed old selection check does not replace a newer successful result with an error (%s)',
    async (origin) => {
      app.dontFailOnErrorResponses()
      const responses = []
      mock
        .onPost('/dashboard/filters/5/options/')
        .reply(() => new Promise((resolve) => responses.push(resolve)))
      let first
      if (origin === 'cached picker') {
        filters = [{ ...filter, values: ['Gone'] }]
        store.commit('dashboardApplication/SET_FILTERS', filters)
        // Opening captures the selection; closing does not cancel this request.
        first = store.dispatch('dashboardApplication/fetchFilterOptions', {
          filterId: 5,
          useCache: true,
          selected: ['Gone'],
        })
      } else {
        first = select(['Gone'])
      }
      await vi.waitFor(() => expect(responses).toHaveLength(1))
      const second = select(['Off-page'])
      await vi.waitFor(() => expect(responses).toHaveLength(2))
      responses[1]([200, { available: ['Off-page'] }])
      await second
      responses[0]([500])
      await first
      expect(options()).toMatchObject({ error: false, unavailable: [] })
    }
  )

  test('preserves membership discovered while a continuation is pending', async () => {
    store.commit('dashboardApplication/SET_FILTER_OPTIONS', {
      filterId: 5,
      values: { next: 'page-2' },
    })
    let finishPage
    mock.onPost('/dashboard/filters/5/options/').reply(({ data }) => {
      const request = JSON.parse(data)
      if (request.after === 'page-2')
        return new Promise((resolve) => {
          finishPage = resolve
        })
      return [200, { available: [] }]
    })
    const page = store.dispatch('dashboardApplication/fetchFilterOptions', {
      filterId: 5,
      more: true,
    })
    await vi.waitFor(() => expect(finishPage).toBeTypeOf('function'))
    await select(['Gone'])
    finishPage([
      200,
      {
        results: ['Sales'],
        next: null,
        snapshot: 'another-token-for-the-same-snapshot',
        available: ['Design'],
      },
    ])
    await page
    expect(options()).toMatchObject({
      snapshot: 'snapshot-a',
      results: ['Design', 'Sales'],
      next: null,
      unavailable: ['Gone'],
    })
  })

  test('checks selections changed while a replacement snapshot was loading', async () => {
    let finishPage
    mock.onPost('/dashboard/filters/5/options/').reply(
      () =>
        new Promise((resolve) => {
          finishPage = resolve
        })
    )
    const page = store.dispatch('dashboardApplication/fetchFilterOptions', {
      filterId: 5,
    })
    await vi.waitFor(() => expect(finishPage).toBeTypeOf('function'))
    await select(['Gone'])
    mock.onPost('/dashboard/filters/5/options/').reply(200, { available: [] })
    finishPage([
      200,
      {
        results: ['Design'],
        next: null,
        snapshot: 'snapshot-b',
        available: ['Design'],
      },
    ])
    await page
    expect(options()).toMatchObject({
      snapshot: 'snapshot-b',
      unavailable: ['Gone'],
    })
  })

  test('a failed membership check remains visible and Retry recovers without declaring missing values', async () => {
    app.dontFailOnErrorResponses()
    mock
      .onPost('/dashboard/filters/5/options/')
      .reply(400, { error: 'ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED' })
    await select(['Gone'])
    expect(options()).toMatchObject({
      error: true,
      errorCode: 'ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED',
      unavailable: [],
      results: ['Design'],
    })
    mock.onPost('/dashboard/filters/5/options/').reply(200, {
      results: ['Gone'],
      next: null,
      snapshot: 'snapshot-b',
      available: ['Gone'],
    })
    await store.dispatch('dashboardApplication/fetchFilterOptions', {
      filterId: 5,
    })
    expect(options()).toMatchObject({
      error: false,
      unavailable: [],
      results: ['Gone'],
    })
  })
})
