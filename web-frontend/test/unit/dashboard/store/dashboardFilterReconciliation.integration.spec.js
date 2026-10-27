import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardFilters from '@baserow/modules/dashboard/components/filter/DashboardFilters'

describe('dashboard filter configuration reconciliation', () => {
  let testApp, store, mock, filters
  const country = {
    id: 5,
    dashboard_id: 1,
    label: 'Country',
    type: 'text',
    operator: 'equal',
    mode: 'dropdown',
    multiple: true,
    values: [],
    formula_value: { formula: 'France, Belgium', mode: 'simple' },
  }
  const channel = { ...country, id: 6, label: 'Channel' }

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    mock = testApp.mock
    filters = [country, channel]
    mock.onGet('/dashboard/1/filters/').reply(() => [200, filters])
    for (const id of [5, 6, 7]) {
      mock.onPatch(`/dashboard/filters/${id}/`).reply(({ data }) => {
        filters = filters.map((filter) =>
          filter.id === id ? { ...filter, ...JSON.parse(data) } : filter
        )
        return [200, filters.find((filter) => filter.id === id)]
      })
    }
    mock.onGet('/dashboard/1/widgets/').reply(200, [])
    mock.onGet('/dashboard/1/data-sources/').reply(200, [])
    for (const id of [5, 6]) {
      mock.onPost(`/dashboard/filters/${id}/options/`).reply(200, {
        results: ['France', 'Belgium'],
        next: null,
        available: [],
      })
    }
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: 1,
      forEditing: false,
    })
    mock.resetHistory()
  })

  afterEach(() => testApp.afterEach())

  test('a delayed PATCH response cannot undo a newer realtime configuration', async () => {
    let finishUpdate
    mock.onPatch('/dashboard/filters/5/').reply(({ data }) => {
      const changes = JSON.parse(data)
      if ('values' in changes) {
        filters = [{ ...filters[0], ...changes }, channel]
        return [200, filters[0]]
      }
      return new Promise((resolve) => {
        finishUpdate = resolve
      })
    })
    const update = store.dispatch('dashboardApplication/updateFilter', {
      filterId: 5,
      values: { label: 'Renamed country' },
    })
    await vi.waitFor(() => expect(finishUpdate).toBeTypeOf('function'))
    const saved = { ...country, label: 'Renamed country' }
    filters = [{ ...saved, mode: 'input' }, channel]
    await store.dispatch('dashboardApplication/handleFiltersUpdated')
    await store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['France'],
    })
    finishUpdate([200, saved])
    await update

    expect(store.getters['dashboardApplication/getFilters'][0]).toEqual(
      filters[0]
    )
    expect(
      store.getters['dashboardApplication/getAppliedFilterValues'](5)
    ).toEqual(['France'])
  })

  test('a delayed realtime snapshot cannot overwrite newer saves awaiting synchronization', async () => {
    let finishRealtime
    mock.onGet('/dashboard/1/filters/').reply(() => {
      if (finishRealtime) return [200, filters]
      return new Promise((resolve) => {
        finishRealtime = resolve
      })
    })
    const realtime = store.dispatch('dashboardApplication/handleFiltersUpdated')
    await vi.waitFor(() => expect(finishRealtime).toBeTypeOf('function'))
    const old = filters
    mock.onPatch('/dashboard/filters/5/').reply(({ data }) => {
      filters = [{ ...filters[0], ...JSON.parse(data) }, channel]
      return [200, filters[0]]
    })
    const selection = store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['France'],
    })
    await flushPromises()
    const configuration = store.dispatch('dashboardApplication/updateFilter', {
      filterId: 5,
      values: { operator: 'not_equal' },
    })
    await flushPromises()
    expect(store.getters['dashboardApplication/getFilters'][0]).toMatchObject({
      operator: 'not_equal',
      values: ['France'],
    })
    // Both saves have their current filters, but still await the source
    // synchronization required by the earlier realtime event.
    finishRealtime([200, old])
    await Promise.all([realtime, selection, configuration])

    expect(store.getters['dashboardApplication/getFilters'][0]).toEqual(
      filters[0]
    )
    expect(
      store.getters['dashboardApplication/getAppliedFilterValues'](5)
    ).toEqual(['France'])
  })

  test('renaming another filter preserves an open dropdown and its draft', async () => {
    const wrapper = await testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard: { id: 1, workspace: { id: 1 } } },
    })
    await wrapper.findAll('.dropdown__selected')[0].trigger('click')
    await flushPromises()
    await testApp.body.findAll('input[type="checkbox"]')[1].setValue(true)
    filters = [country, { ...channel, label: 'Renamed channel' }]
    await store.dispatch('dashboardApplication/handleFiltersUpdated')
    await flushPromises()

    expect(
      testApp.body
        .findAll('.dashboard-filter__option-value')
        .map((option) => option.text())
    ).toEqual(['France', 'Belgium'])
    expect(
      testApp.body
        .findAll('input[type="checkbox"]')
        .map((checkbox) => checkbox.element.checked)
    ).toEqual([false, true])
    expect(testApp.body.find('[role="status"]').exists()).toBe(false)
    expect(
      mock.history.post.filter(({ url }) => url.endsWith('/options/'))
    ).toHaveLength(0)
  })

  test.each([
    { formula: 'France, Canada', mode: 'simple' },
    { formula: 'France, Belgium', mode: 'raw' },
  ])(
    'reloads changed option formulas in an open picker: %j',
    async (formula) => {
      const wrapper = await testApp.mount(DashboardFilters, {
        global: { stubs: { Teleport: false } },
        props: { dashboard: { id: 1, workspace: { id: 1 } } },
      })
      await wrapper.findAll('.dropdown__selected')[0].trigger('click')
      await flushPromises()
      await testApp.body.findAll('input[type="checkbox"]')[1].setValue(true)
      let finishOptions
      mock.onPost('/dashboard/filters/5/options/').reply(
        () =>
          new Promise((resolve) => {
            finishOptions = resolve
          })
      )
      filters = [{ ...country, formula_value: formula }, channel]
      await store.dispatch('dashboardApplication/handleFiltersUpdated')
      await flushPromises()

      expect(testApp.body.get('[role="status"]').text()).toBe(
        'dashboardFilter.loading'
      )
      finishOptions([
        200,
        { results: ['France', 'Canada'], next: null, available: ['Belgium'] },
      ])
      await flushPromises()
      expect(
        testApp.body
          .findAll('.dashboard-filter__option-value')
          .map((option) => option.text())
      ).toEqual(['France', 'Canada', 'Belgium'])
      expect(
        testApp.body
          .findAll('input[type="checkbox"]')
          .map((checkbox) => checkbox.element.checked)
      ).toEqual([false, false, true])
      expect(testApp.body.find('[role="status"]').exists()).toBe(false)
      expect(
        mock.history.post
          .filter(({ url }) => url.endsWith('/options/'))
          .map(({ url, data }) => [url, JSON.parse(data)])
      ).toEqual([['/dashboard/filters/5/options/', { selected: ['Belgium'] }]])
    }
  )

  test('opens the new filter settings when realtime supersedes its collection request', async () => {
    const created = { ...country, id: 7, label: 'New filter' }
    mock.onPost('/dashboard/1/filters/').reply(() => {
      filters = [...filters, created]
      return [200, created]
    })
    const responses = []
    mock.onGet('/dashboard/1/filters/').reply(() => {
      if (responses.length >= 2) return [200, filters]
      return new Promise((resolve) => {
        responses.push(resolve)
      })
    })
    const create = store.dispatch('dashboardApplication/createFilter', {
      label: 'New filter',
      type: 'text',
    })
    await vi.waitFor(() => expect(responses).toHaveLength(1))
    const realtime = store.dispatch('dashboardApplication/handleFiltersUpdated')
    await vi.waitFor(() => expect(responses).toHaveLength(2))
    responses[0]([200, filters])
    await flushPromises()
    responses[1]([200, filters])
    await Promise.all([create, realtime])

    expect(store.getters['dashboardApplication/isEditMode']).toBe(true)
    expect(store.getters['dashboardApplication/getSelectedFilter']).toEqual(
      created
    )
  })

  test.each([
    { label: 'Country', mode: 'dropdown', multiple: true },
    { label: 'C'.repeat(255), mode: 'input', multiple: false },
  ])(
    'duplicates a $mode filter with independent configuration and selection',
    async (configuration) => {
      const original = {
        ...country,
        ...configuration,
        operator: 'not_equal',
        formula_value: { formula: "get('table.42.field_51')", mode: 'raw' },
      }
      const firstCopyName = `${original.label.slice(0, 253)} 1`
      filters = [original, { ...channel, label: firstCopyName }]
      await store.dispatch('dashboardApplication/handleFiltersUpdated')
      await store.dispatch('dashboardApplication/applyFilter', {
        filterId: original.id,
        values: ['France'],
      })
      await store.dispatch('dashboardApplication/enterEditMode')
      mock.resetHistory()
      let finishCreate
      mock.onPost('/dashboard/1/filters/').reply(
        () =>
          new Promise((resolve) => {
            finishCreate = resolve
          })
      )
      const wrapper = await testApp.mount(DashboardFilters, {
        global: { stubs: { Teleport: false } },
        props: { dashboard: { id: 1, workspace: { id: 1 } } },
      })
      const trigger = wrapper.findAll(
        '[aria-label="dashboardFilter.actions"]'
      )[0]
      await trigger.trigger('click')
      await flushPromises()
      await testApp.body.get('button:has(.iconoir-copy)').trigger('click')
      await flushPromises()
      expect(trigger.attributes('disabled')).toBeDefined()
      const payload = JSON.parse(
        mock.history.post.find(({ url }) => url === '/dashboard/1/filters/')
          .data
      )
      expect(payload).toEqual({
        label: `${original.label.slice(0, 253)} 2`,
        type: 'text',
        operator: 'not_equal',
        mode: configuration.mode,
        multiple: configuration.multiple,
        formula_value: original.formula_value,
        values: ['France'],
      })
      const created = { ...payload, id: 7, dashboard_id: 1 }
      filters = [...filters, created]
      finishCreate([201, created])
      await flushPromises()

      expect(wrapper.findAll('.dashboard-filter')).toHaveLength(3)
      expect(store.getters['dashboardApplication/getSelectedFilter']).toEqual(
        created
      )
      expect(
        store.getters['dashboardApplication/getAppliedFilterValues'](7)
      ).toEqual(['France'])
      expect(
        store.getters['dashboardApplication/getAppliedFilterValues'](
          original.id
        )
      ).toEqual(['France'])
      expect(store.getters['dashboardApplication/getFilters'][0]).toEqual({
        ...original,
        values: ['France'],
      })
      expect(mock.history.patch).toHaveLength(0)
      expect(trigger.attributes('disabled')).toBeUndefined()

      await store.dispatch('dashboardApplication/applyFilter', {
        filterId: 7,
        values: ['Belgium'],
      })
      expect(
        store.getters['dashboardApplication/getAppliedFilterValues'](7)
      ).toEqual(['Belgium'])
      expect(
        store.getters['dashboardApplication/getAppliedFilterValues'](
          original.id
        )
      ).toEqual(['France'])
    }
  )
})
