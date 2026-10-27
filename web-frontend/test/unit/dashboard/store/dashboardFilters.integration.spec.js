import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardFilters from '@baserow/modules/dashboard/components/filter/DashboardFilters'
import Toasts from '@baserow/modules/core/components/toasts/Toasts'

const { hasPermission } = vi.hoisted(() => ({ hasPermission: vi.fn() }))
vi.mock('#app', async (importOriginal) => {
  const original = await importOriginal()
  return {
    ...original,
    useNuxtApp: (...args) =>
      new Proxy(original.useNuxtApp(...args), {
        get: (app, key) =>
          key === '$hasPermission' ? hasPermission : app[key],
      }),
  }
})

describe('dashboard text filters', () => {
  let store, mock, testApp, serverFilters
  const dashboardId = 1
  const widgets = [
    { id: 2, dashboard_id: 1, data_source_id: 10, type: 'summary' },
    { id: 3, dashboard_id: 1, data_source_id: 10, type: 'summary' },
  ]
  const filter = {
    id: 5,
    dashboard_id: 1,
    label: 'Team',
    type: 'text',
    operator: 'equal',
    mode: 'dropdown',
    multiple: true,
    values: [],
    formula_value: { formula: "get('table.1.*.field_20')", mode: 'simple' },
  }

  beforeEach(async () => {
    hasPermission.mockReturnValue(true)
    testApp = new TestApp()
    testApp.authenticate({ id: 1 })
    store = testApp.store
    mock = testApp.mock
    mock.onGet('/dashboard/1/filters/').reply(() => [200, serverFilters])
    for (const id of [5, 6]) {
      mock.onPatch(`/dashboard/filters/${id}/`).reply(({ data }) => {
        serverFilters = serverFilters.map((filter) =>
          filter.id === id ? { ...filter, ...JSON.parse(data) } : filter
        )
        return [200, serverFilters.find((filter) => filter.id === id)]
      })
    }
    mock.onGet('/dashboard/1/widgets/').reply(200, widgets)
    serverFilters = [{ ...filter, mode: 'input' }]
    mock
      .onGet('/dashboard/1/data-sources/')
      .reply(200, [{ id: 10, dashboard_id: 1 }])
    mock
      .onPost('/dashboard/data-sources/10/dispatch/')
      .reply(200, { result: 10 })
    mock
      .onPost('/dashboard/filters/5/options/')
      .reply(200, { results: [], next: null, available: [] })
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId,
      forEditing: false,
    })
    // Begin after enabling a dropdown, before its first options request.
    // Initial preloading is covered in dashboardFilterPreload.integration.spec.
    serverFilters = [filter]
    await store.dispatch('dashboardApplication/fetchFilters')
    mock.resetHistory()
  })
  afterEach(async () => {
    await testApp.afterEach()
  })

  async function renderFilters() {
    const wrapper = await testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: dashboardId, workspace: { id: 1 } } },
    })
    const notifications = await testApp.mount(Toasts)
    return { wrapper, notifications }
  }

  test.each([
    ['updateFilter', {}, { mode: 'input' }, ['Design', 'Sales']],
    ['updateFilter', {}, { multiple: false }, ['Design']],
    ['updateFilter', { mode: 'input' }, { mode: 'dropdown' }, ['Design']],
    ['updateFilter', { multiple: false }, { multiple: true }, ['Design']],
    ['handleFiltersUpdated', {}, { mode: 'input' }, ['Design']],
    ['handleFiltersUpdated', {}, { multiple: false }, ['Design', 'Sales']],
    [
      'handleFiltersUpdated',
      { mode: 'input' },
      { mode: 'dropdown' },
      ['Design'],
    ],
    [
      'handleFiltersUpdated',
      { multiple: false },
      { multiple: true },
      ['Design'],
    ],
  ])(
    '%s clears the selection for %j → %j without a reset toast or clearing other filters',
    async (action, initial, changes, values) => {
      const current = { ...filter, ...initial }
      const other = { ...filter, id: 6, label: 'Status' }
      serverFilters = [current, other]
      await store.dispatch('dashboardApplication/fetchFilters')
      await store.dispatch('dashboardApplication/applyFilter', {
        filterId: 5,
        values,
      })
      await store.dispatch('dashboardApplication/applyFilter', {
        filterId: 6,
        values: ['Open'],
      })
      const { wrapper, notifications } = await renderFilters()
      const updated = { ...current, ...changes, values: [] }
      mock.onPatch('/dashboard/filters/5/').reply(200, updated)
      serverFilters = [updated, { ...other, values: ['Open'] }]
      await store.dispatch(`dashboardApplication/${action}`, {
        filterId: 5,
        values: changes,
      })
      await flushPromises()
      expect(
        wrapper.findAll('.dashboard-filter__value').map((value) => value.text())
      ).toEqual(['dashboardFilter.choose', 'Open'])
      expect(notifications.find('.toast').exists()).toBe(false)
      expect(
        JSON.parse(
          mock.history.post
            .filter(({ url }) => url.endsWith('/dispatch/'))
            .at(-1).data
        )
      ).toEqual({})
      await store.dispatch('dashboardApplication/handleFiltersUpdated')
      await flushPromises()
      expect(notifications.find('.toast').exists()).toBe(false)
    }
  )

  test.each([
    [{}, { label: 'Renamed' }],
    [{}, { operator: 'contains' }],
    [
      {},
      {
        formula_value: { formula: "get('table.1.*.field_21')", mode: 'simple' },
      },
    ],
    [{}, { mode: 'dropdown', multiple: true }],
  ])(
    'preserves the selection for other configuration changes: %j → %j',
    async (initial, changes) => {
      const current = { ...filter, ...initial }
      serverFilters = [current]
      await store.dispatch('dashboardApplication/fetchFilters')
      await store.dispatch('dashboardApplication/applyFilter', {
        filterId: 5,
        values: ['Design'],
      })
      const { wrapper, notifications } = await renderFilters()
      mock
        .onPatch('/dashboard/filters/5/')
        .reply(200, { ...current, ...changes, values: ['Design'] })
      serverFilters = [{ ...current, ...changes, values: ['Design'] }]
      await store.dispatch('dashboardApplication/updateFilter', {
        filterId: 5,
        values: changes,
      })
      await flushPromises()
      expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
      expect(notifications.find('.toast').exists()).toBe(false)
    }
  )

  test('keeps selections while the configuration update is pending or fails', async () => {
    testApp.dontFailOnErrorResponses()
    await store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['Design'],
    })
    const { wrapper, notifications } = await renderFilters()
    let finish
    mock.onPatch('/dashboard/filters/5/').reply(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const update = store
      .dispatch('dashboardApplication/updateFilter', {
        filterId: 5,
        values: { mode: 'input' },
      })
      .catch((error) => error)
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'))
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
    expect(notifications.find('.toast').exists()).toBe(false)
    finish([500])
    expect(await update).toBeInstanceOf(Error)
    await flushPromises()
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
    expect(notifications.find('.toast').exists()).toBe(false)
  })

  test.each([{ mode: 'input' }, { multiple: false }])(
    'discards an open draft when another editor changes the filter to %j',
    async (changes) => {
      mock.onPost('/dashboard/filters/5/options/').reply(200, {
        results: ['Design', 'Sales'],
        next: null,
        available: [],
      })
      const { wrapper, notifications } = await renderFilters()
      await wrapper.get('.dropdown__selected').trigger('click')
      await flushPromises()
      await testApp.body.findAll('input[type="checkbox"]')[1].setValue(true)
      serverFilters = [{ ...filter, ...changes }]
      await store.dispatch('dashboardApplication/handleFiltersUpdated')
      await flushPromises()
      expect(
        wrapper.get('.dropdown__selected').attributes('aria-expanded')
      ).toBe('false')
      expect(notifications.find('.toast').exists()).toBe(false)
      await wrapper.get('.dropdown__selected').trigger('click')
      await flushPromises()
      if (changes.mode === 'input') {
        expect(
          testApp.body.get('.dashboard-filter__input input').element.value
        ).toBe('')
      } else {
        expect(testApp.body.find('[aria-pressed="true"]').exists()).toBe(false)
      }
      expect(testApp.body.get('button[type="submit"]').element.disabled).toBe(
        true
      )
    }
  )

  test('does not announce a reset when the filter has no selection or draft', async () => {
    const { notifications } = await renderFilters()
    mock
      .onPatch('/dashboard/filters/5/')
      .reply(200, { ...filter, mode: 'input' })
    serverFilters = [{ ...filter, mode: 'input' }]
    await store.dispatch('dashboardApplication/updateFilter', {
      filterId: 5,
      values: { mode: 'input' },
    })
    await flushPromises()
    expect(notifications.find('.toast').exists()).toBe(false)
  })

  test('does not announce a reset after the selection was already cleared outside the picker', async () => {
    await store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['Design'],
    })
    const { wrapper, notifications } = await renderFilters()
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    await testApp.body.get('form').trigger('keydown', { key: 'Escape' })
    await wrapper.get('[aria-label="dashboardFilter.clear"]').trigger('click')
    await flushPromises()
    mock
      .onPatch('/dashboard/filters/5/')
      .reply(200, { ...filter, mode: 'input' })
    serverFilters = [{ ...filter, mode: 'input' }]
    await store.dispatch('dashboardApplication/updateFilter', {
      filterId: 5,
      values: { mode: 'input' },
    })
    await flushPromises()
    expect(notifications.find('.toast').exists()).toBe(false)
  })

  test.each([{ results: [] }, { results: ['Design'] }])(
    'reuses loaded options $results until Refresh while preserving selections',
    async ({ results }) => {
      mock
        .onPost('/dashboard/filters/5/options/')
        .reply(200, { results, next: null, available: ['Design'] })
      const open = () =>
        store.dispatch('dashboardApplication/fetchFilterOptions', {
          filterId: 5,
          useCache: true,
        })
      await open()
      await store.dispatch('dashboardApplication/applyFilter', {
        filterId: 5,
        values: ['Design'],
      })
      mock
        .onPost('/dashboard/filters/5/options/')
        .reply(200, { results: ['Sales'], next: null, available: [] })
      await open()
      expect(
        store.getters['dashboardApplication/getFilterOptions'](5)
      ).toMatchObject({ results, loading: false })
      expect(
        mock.history.post.filter(({ url }) => url.endsWith('/options/'))
      ).toHaveLength(1)

      await store.dispatch('dashboardApplication/refresh')
      await open()
      expect(
        store.getters['dashboardApplication/getFilterOptions'](5)
      ).toMatchObject({
        results: ['Sales'],
        unavailable: ['Design'],
        loading: false,
      })
      expect(
        store.getters['dashboardApplication/getAppliedFilterValues'](5)
      ).toEqual(['Design'])
      expect(
        mock.history.post.filter(({ url }) => url.endsWith('/options/'))
      ).toHaveLength(2)
    }
  )

  test('shares source results and preserves applied values on refresh and reload', async () => {
    await store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['Design'],
    })
    expect(
      store.getters['dashboardApplication/getDataForDataSource'](10)
    ).toEqual({
      result: 10,
    })
    const lastDispatch = mock.history.post
      .filter(({ url }) => url.endsWith('/dispatch/'))
      .at(-1)
    expect(JSON.parse(mock.history.patch.at(-1).data)).toEqual({
      values: ['Design'],
    })
    expect(JSON.parse(lastDispatch.data)).toEqual({})
    await store.dispatch('dashboardApplication/refresh')
    expect(
      store.getters['dashboardApplication/getAppliedFilterValues'](5)
    ).toEqual(['Design'])
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId,
      forEditing: false,
    })
    const { wrapper } = await renderFilters()
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
    expect(
      JSON.parse(
        mock.history.post.filter(({ url }) => url.endsWith('/dispatch/')).at(-1)
          .data
      )
    ).toEqual({})
  })

  test('filters loaded pages locally and keeps the search when more choices load or refresh', async () => {
    mock.onPost('/dashboard/filters/5/options/').reply(({ data }) => {
      const { after } = JSON.parse(data)
      return [
        200,
        {
          results:
            after === 'Sales' ? ['Support'] : after ? ['Sales'] : ['Design'],
          next: after === 'Sales' ? null : after ? 'Sales' : 'Design',
          available: [],
        },
      ]
    })
    const wrapper = await testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: dashboardId, workspace: { id: 1 } } },
    })
    const open = async () => {
      await wrapper.get('.dropdown__selected').trigger('click')
      await flushPromises()
    }
    const search = async (value) => {
      await testApp.body.get('input[type="text"]').setValue(value)
    }
    const choices = () =>
      testApp.body
        .findAll('.dashboard-filter__option-value')
        .map((v) => v.text())
    const optionRequests = () =>
      mock.history.post.filter(({ url }) => url.endsWith('/options/'))

    await open()
    await search('sAL')
    expect(choices()).toEqual([])
    expect(optionRequests()).toHaveLength(1)
    await testApp.body.get('.dashboard-filter__more').trigger('click')
    await flushPromises()
    expect(choices()).toEqual(['Sales'])
    expect(JSON.parse(optionRequests()[1].data)).toEqual({
      after: 'Design',
      selected: [],
    })
    await search('')
    expect(choices()).toEqual(['Design', 'Sales'])
    expect(optionRequests()).toHaveLength(2)

    await search('Sales')
    await testApp.body.get('form').trigger('keydown', { key: 'Escape' })
    await open()
    expect(testApp.body.get('input[type="text"]').element.value).toBe('')
    expect(choices()).toEqual(['Design', 'Sales'])
    expect(testApp.body.find('[role="status"]').exists()).toBe(false)
    expect(optionRequests()).toHaveLength(2)
    await testApp.body.get('.dashboard-filter__more').trigger('click')
    await flushPromises()
    expect(JSON.parse(optionRequests()[2].data).after).toBe('Sales')
    await search('port')
    expect(choices()).toEqual(['Support'])
    mock.onPost('/dashboard/filters/5/options/').reply(200, {
      results: ['Support', 'Transport'],
      next: null,
      available: [],
    })
    await store.dispatch('dashboardApplication/refresh')
    await flushPromises()
    expect(testApp.body.get('input[type="text"]').element.value).toBe('port')
    expect(choices()).toEqual(['Support', 'Transport'])
    expect(testApp.body.find('[role="status"]').exists()).toBe(false)
    expect(optionRequests()).toHaveLength(4)
  })

  test('deletes a filter through its menu and prevents duplicate deletion while pending', async () => {
    let finishDelete
    mock.onDelete('/dashboard/filters/5/').reply(
      () =>
        new Promise((resolve) => {
          finishDelete = resolve
        })
    )
    await store.dispatch('dashboardApplication/enterEditMode')
    const wrapper = await testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: dashboardId, workspace: { id: 1 } } },
    })
    const trigger = wrapper.get('[aria-label="dashboardFilter.actions"]')
    await trigger.trigger('click')
    await flushPromises()
    await testApp.body.get('.context__menu-item-link--delete').trigger('click')
    await flushPromises()
    expect(mock.history.delete).toHaveLength(1)
    expect(trigger.element.disabled).toBe(true)
    expect(wrapper.find('.dashboard-filter').exists()).toBe(true)
    serverFilters = []
    finishDelete([204])
    await flushPromises()
    expect(wrapper.find('.dashboard-filter').exists()).toBe(false)
  })

  test('keeps a filter and allows retrying when deletion fails', async () => {
    testApp.dontFailOnErrorResponses()
    mock.onDelete('/dashboard/filters/5/').replyOnce(500)
    mock.onDelete('/dashboard/filters/5/').reply(() => {
      serverFilters = []
      return [204]
    })
    await store.dispatch('dashboardApplication/enterEditMode')
    const wrapper = await testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: dashboardId, workspace: { id: 1 } } },
    })
    const trigger = wrapper.get('[aria-label="dashboardFilter.actions"]')
    await trigger.trigger('click')
    await flushPromises()
    await testApp.body.get('.context__menu-item-link--delete').trigger('click')
    await flushPromises()
    expect(wrapper.find('.dashboard-filter').exists()).toBe(true)
    expect(trigger.element.disabled).toBe(false)
    await trigger.trigger('click')
    await flushPromises()
    await testApp.body.get('.context__menu-item-link--delete').trigger('click')
    await flushPromises()
    expect(wrapper.find('.dashboard-filter').exists()).toBe(false)
    expect(mock.history.delete).toHaveLength(2)
  })

  test.each([
    { canCreate: true, canDelete: false },
    { canCreate: false, canDelete: true },
    { canCreate: false, canDelete: false },
  ])(
    'only shows permitted filter actions: %j',
    async ({ canCreate, canDelete }) => {
      hasPermission.mockImplementation((operation) => {
        if (operation === 'dashboard.create_filter') return canCreate
        if (operation === 'dashboard.filter.delete') return canDelete
        return true
      })
      await store.dispatch('dashboardApplication/enterEditMode')
      const dashboard = { id: dashboardId, workspace: { id: 1 } }
      const wrapper = await testApp.mount(DashboardFilters, {
        global: { stubs: { Teleport: false } },
        props: { dashboard },
      })
      const trigger = wrapper.find('[aria-label="dashboardFilter.actions"]')
      expect(trigger.exists()).toBe(canCreate || canDelete)
      if (trigger.exists()) {
        await trigger.trigger('click')
        await flushPromises()
        expect(testApp.body.find('button:has(.iconoir-copy)').exists()).toBe(
          canCreate
        )
        expect(
          testApp.body.find('.context__menu-item-link--delete').exists()
        ).toBe(canDelete)
      }
      expect(hasPermission).toHaveBeenCalledWith(
        'dashboard.create_filter',
        dashboard,
        1
      )
      expect(hasPermission).toHaveBeenCalledWith(
        'dashboard.filter.delete',
        filter,
        1
      )
      expect(mock.history.delete).toHaveLength(0)
    }
  )

  test('reopening does not restart an initial load or an explicit Refresh', async () => {
    let resolveOptions
    mock.onPost('/dashboard/filters/5/options/').reply(
      () =>
        new Promise((resolve) => {
          resolveOptions = resolve
        })
    )
    const open = () =>
      store.dispatch('dashboardApplication/fetchFilterOptions', {
        filterId: 5,
        useCache: true,
      })
    const initial = open()
    await vi.waitFor(() => expect(resolveOptions).toBeTypeOf('function'))
    await open()
    expect(
      mock.history.post.filter(({ url }) => url.endsWith('/options/'))
    ).toHaveLength(1)
    resolveOptions([200, { results: ['Design'], next: null, available: [] }])
    await initial

    resolveOptions = undefined
    const refresh = store.dispatch('dashboardApplication/refresh')
    await vi.waitFor(() => expect(resolveOptions).toBeTypeOf('function'))
    await open()
    resolveOptions([200, { results: ['Sales'], next: null, available: [] }])
    await refresh
    await open()
    expect(
      mock.history.post.filter(({ url }) => url.endsWith('/options/'))
    ).toHaveLength(2)
    expect(
      store.getters['dashboardApplication/getFilterOptions'](5)
    ).toMatchObject({
      results: ['Sales'],
      loading: false,
    })
  })

  test.each(['page', 'refresh'])(
    'discards a previous page when %s finishes first during Refresh',
    async (first) => {
      mock.onPost('/dashboard/filters/5/options/').reply(200, {
        results: ['Design'],
        next: 'Design',
        available: [],
      })
      await store.dispatch('dashboardApplication/fetchFilterOptions', {
        filterId: 5,
      })
      const responses = {}
      mock.onPost('/dashboard/filters/5/options/').reply(
        ({ data }) =>
          new Promise((resolve) => {
            responses[JSON.parse(data).after ? 'page' : 'refresh'] = resolve
          })
      )
      const page = store.dispatch('dashboardApplication/fetchFilterOptions', {
        filterId: 5,
        more: true,
      })
      await vi.waitFor(() => expect(responses.page).toBeTypeOf('function'))
      const refresh = store.dispatch('dashboardApplication/refresh')
      await vi.waitFor(() => expect(responses.refresh).toBeTypeOf('function'))
      const finishPage = () =>
        responses.page([200, { results: ['Sales'], next: null, available: [] }])
      if (first === 'page') {
        finishPage()
        await page
      }
      responses.refresh([
        200,
        { results: ['Marketing'], next: null, available: [] },
      ])
      await refresh
      if (first === 'refresh') {
        finishPage()
        await page
      }
      await store.dispatch('dashboardApplication/fetchFilterOptions', {
        filterId: 5,
        useCache: true,
      })
      expect(
        store.getters['dashboardApplication/getFilterOptions'](5)
      ).toMatchObject({
        results: ['Marketing'],
        next: null,
        loading: false,
      })
      expect(
        mock.history.post.filter(({ url }) => url.endsWith('/options/'))
      ).toHaveLength(3)
    }
  )

  test.each(['updateFilter', 'handleFiltersUpdated'])(
    'invalidates cached choices after %s changes the filter configuration',
    async (action) => {
      mock.onPost('/dashboard/filters/5/options/').reply(200, {
        results: ['Design'],
        next: null,
        available: [],
      })
      const open = () =>
        store.dispatch('dashboardApplication/fetchFilterOptions', {
          filterId: 5,
          useCache: true,
        })
      await open()
      const changed = {
        ...filter,
        formula_value: { formula: "get('table.1.*.field_21')", mode: 'simple' },
      }
      mock.onPatch('/dashboard/filters/5/').reply(200, changed)
      serverFilters = [changed]
      await store.dispatch(`dashboardApplication/${action}`, {
        filterId: 5,
        values: { formula_value: changed.formula_value },
      })
      mock.onPost('/dashboard/filters/5/options/').reply(200, {
        results: ['Marketing'],
        next: null,
        available: [],
      })
      await open()
      expect(
        store.getters['dashboardApplication/getFilterOptions'](5).results
      ).toEqual(['Marketing'])
      expect(
        mock.history.post.filter(({ url }) => url.endsWith('/options/'))
      ).toHaveLength(2)
    }
  )

  test('ignores a source response from before the latest Apply', async () => {
    let resolveOld
    mock.onPost('/dashboard/data-sources/10/dispatch/').reply(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve
        })
    )
    const old = store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['Design'],
    })
    await vi.waitFor(() => expect(resolveOld).toBeTypeOf('function'))
    mock
      .onPost('/dashboard/data-sources/10/dispatch/')
      .reply(200, { result: 99 })
    await store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['Sales'],
    })
    resolveOld([200, { result: 1 }])
    await old
    expect(
      store.getters['dashboardApplication/getDataForDataSource'](10)
    ).toEqual({
      result: 99,
    })
  })

  test('ignores stale option loads and does not infer absence from failures', async () => {
    let resolveOld
    mock.onPost('/dashboard/filters/5/options/').reply(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve
        })
    )
    const old = store.dispatch('dashboardApplication/fetchFilterOptions', {
      filterId: 5,
      selected: ['Design'],
    })
    await vi.waitFor(() => expect(resolveOld).toBeTypeOf('function'))
    mock
      .onPost('/dashboard/filters/5/options/')
      .reply(200, { results: ['Sales'], next: null, available: ['Design'] })
    await store.dispatch('dashboardApplication/fetchFilterOptions', {
      filterId: 5,
      selected: ['Design'],
    })
    resolveOld([200, { results: [], next: null, available: [] }])
    await old
    const options = () =>
      store.getters['dashboardApplication/getFilterOptions'](5)
    expect(options().results).toEqual(['Sales'])
    expect(options().unavailable).toEqual([])
    mock.onPost('/dashboard/filters/5/options/').reply(500)
    await store.dispatch('dashboardApplication/fetchFilterOptions', {
      filterId: 5,
      selected: ['Design'],
    })
    expect(options()).toMatchObject({
      error: true,
      loading: false,
      unavailable: [],
    })
  })

  test('keeps an options request when the configuration is unchanged', async () => {
    let resolveOptions
    mock.onPost('/dashboard/filters/5/options/').reply(
      () =>
        new Promise((resolve) => {
          resolveOptions = resolve
        })
    )
    const request = store.dispatch('dashboardApplication/fetchFilterOptions', {
      filterId: 5,
    })
    await vi.waitFor(() => expect(resolveOptions).toBeTypeOf('function'))
    await store.dispatch('dashboardApplication/fetchFilters')
    resolveOptions([200, { results: ['Old'], next: null, available: [] }])
    await request
    expect(
      store.getters['dashboardApplication/getFilterOptions'](5)
    ).toMatchObject({ loading: false, results: ['Old'] })
  })

  test.each(['deleteFilter', 'handleFiltersUpdated'])(
    '%s refreshes source conditions and ignores a previous save response',
    async (action) => {
      const source = {
        id: 10,
        dashboard_id: 1,
        filters: [
          {
            field: 20,
            type: 'equal',
            value: { formula: "get('dashboard_filter.5')", mode: 'simple' },
          },
        ],
      }
      mock.onGet('/dashboard/1/data-sources/').reply(200, [source])
      await store.dispatch('dashboardApplication/fetchNewDataSources', 1)
      let resolveUpdate
      mock.onPatch('/dashboard/data-sources/10/').reply(
        () =>
          new Promise((resolve) => {
            resolveUpdate = resolve
          })
      )
      const update = store.dispatch('dashboardApplication/updateDataSource', {
        dataSourceId: 10,
        values: { filters: source.filters },
      })
      await vi.waitFor(() => expect(resolveUpdate).toBeTypeOf('function'))
      mock
        .onGet('/dashboard/1/data-sources/')
        .reply(200, [{ ...source, filters: [] }])
      serverFilters = []
      mock.onDelete('/dashboard/filters/5/').reply(204)

      await store.dispatch(`dashboardApplication/${action}`, 5)

      expect(
        store.getters['dashboardApplication/getDataSourceById'](10).filters
      ).toEqual([])

      // The save may have succeeded before or after the control deletion.
      // Re-read its latest state so independent edits are also preserved.
      mock
        .onGet('/dashboard/1/data-sources/')
        .reply(200, [{ ...source, name: 'Saved name', filters: [] }])
      resolveUpdate([200, { ...source, name: 'Saved name' }])
      await update
      expect(
        store.getters['dashboardApplication/getDataSourceById'](10)
      ).toMatchObject({ name: 'Saved name', filters: [] })
    }
  )

  test('does not restore a deleted filter from a delayed update response', async () => {
    let resolveUpdate
    mock.onPatch('/dashboard/filters/5/').reply(
      () =>
        new Promise((resolve) => {
          resolveUpdate = resolve
        })
    )
    const update = store.dispatch('dashboardApplication/updateFilter', {
      filterId: 5,
      values: { label: 'Renamed' },
    })
    await vi.waitFor(() => expect(resolveUpdate).toBeTypeOf('function'))
    serverFilters = []
    await store.dispatch('dashboardApplication/handleFiltersUpdated')
    resolveUpdate([200, { ...filter, label: 'Renamed' }])
    await update
    expect(store.getters['dashboardApplication/getFilters']).toEqual([])
  })
})
