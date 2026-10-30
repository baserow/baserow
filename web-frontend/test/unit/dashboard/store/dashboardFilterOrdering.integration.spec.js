import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import { registerRealtimeEvents } from '@baserow/modules/dashboard/realtime'
import DashboardFilters from '@baserow/modules/dashboard/components/filter/DashboardFilters'

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

describe('dashboard filter ordering', () => {
  let testApp, store, mock, filters
  const dashboard = { id: 1, workspace: { id: 1 } }
  const filterIds = () =>
    store.getters['dashboardApplication/getFilters'].map(({ id }) => id)
  const labels = (wrapper) =>
    wrapper
      .findAll('.dashboard-filter .control__label')
      .map((label) => label.text())
  const render = () => testApp.mount(DashboardFilters, { props: { dashboard } })

  beforeEach(async () => {
    hasPermission.mockReturnValue(true)
    testApp = new TestApp()
    store = testApp.store
    mock = testApp.mock
    filters = ['Country', 'Channel', 'Region'].map((label, index) => ({
      id: index + 5,
      order: index + 1,
      dashboard_id: 1,
      label,
      type: 'text',
      operator: 'equal',
      mode: 'dropdown',
      multiple: true,
      values: [],
      formula_value: { formula: 'France, Belgium', mode: 'simple' },
    }))
    mock.onGet('/dashboard/1/filters/').reply(() => [200, [...filters]])
    mock.onPatch('/dashboard/filters/5/').reply(({ data }) => {
      filters = filters.map((filter) =>
        filter.id === 5 ? { ...filter, ...JSON.parse(data) } : filter
      )
      return [200, filters.find(({ id }) => id === 5)]
    })
    mock.onGet('/dashboard/1/widgets/').reply(200, [])
    mock.onGet('/dashboard/1/data-sources/').reply(200, [])
    filters.forEach(({ id }) => {
      mock.onPost(`/dashboard/filters/${id}/options/`).reply(200, {
        results: ['France', 'Belgium'],
        next: null,
        available: [],
      })
    })
    mock.onPost('/dashboard/1/filters/order/').reply(({ data }) => {
      const { order } = JSON.parse(data)
      filters = order.map((id, index) => ({
        ...filters.find((filter) => filter.id === id),
        order: index + 1,
      }))
      return [204]
    })
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: 1,
      forEditing: false,
    })
    await store.dispatch('dashboardApplication/enterEditMode')
    await store.dispatch('dashboardApplication/selectFilter', 5)
    await store.dispatch('dashboardApplication/applyFilter', {
      filterId: 5,
      values: ['France'],
    })
    mock.resetHistory()
  })
  afterEach(() => testApp.afterEach())

  test('drags a filter by its label, persists its order and preserves its values and options', async () => {
    const wrapper = await render()
    const options = store.getters['dashboardApplication/getFilterOptions'](5)
    const controls = wrapper.findAll('.dashboard-filter')
    controls.forEach((control, index) => {
      control.element.getBoundingClientRect = () => ({
        left: index * 200,
        right: index * 200 + 180,
        top: 0,
        bottom: 60,
        width: 180,
        height: 60,
      })
    })
    const handle = controls[0].get('.control__label')
    await handle.trigger('mousedown', { button: 0, clientX: 170, clientY: 10 })
    window.dispatchEvent(
      new MouseEvent('mousemove', { clientX: 590, clientY: 10, bubbles: true })
    )
    window.dispatchEvent(
      new MouseEvent('mouseup', { clientX: 590, clientY: 10, bubbles: true })
    )
    await flushPromises()
    expect(labels(wrapper)).toEqual(['Channel', 'Region', 'Country'])
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ order: [6, 7, 5] })
    expect(mock.history.post).toHaveLength(1)
    expect(mock.history.get.map(({ url }) => url)).toEqual([
      '/dashboard/1/filters/',
      '/dashboard/1/data-sources/',
    ])
    expect(
      store.getters['dashboardApplication/getAppliedFilterValues'](5)
    ).toEqual(['France'])
    expect(store.getters['dashboardApplication/getFilterOptions'](5)).toEqual(
      options
    )
    expect(store.getters['dashboardApplication/getSelectedFilter'].id).toBe(5)
    await store.dispatch('dashboardApplication/fetchFilters')
    expect(labels(wrapper)).toEqual(['Channel', 'Region', 'Country'])
  })

  test('enables dragging labels when switching from view to edit mode', async () => {
    await store.dispatch('dashboardApplication/toggleEditMode')
    const wrapper = await render()
    expect(wrapper.find('.dashboard-filter--movable').exists()).toBe(false)
    await store.dispatch('dashboardApplication/enterEditMode')
    await flushPromises()
    expect(wrapper.findAll('.dashboard-filter--movable')).toHaveLength(3)
  })

  test.each([false, true])(
    'blocks structural actions during a pending reorder without blocking selections (failed: %s)',
    async (failed) => {
      if (failed) testApp.dontFailOnErrorResponses()
      let finishOrder
      mock.onPost('/dashboard/1/filters/order/').reply(({ data }) => {
        const { order } = JSON.parse(data)
        return new Promise((resolve) => {
          finishOrder = () => {
            if (failed) return resolve([500])
            const missing = order.some(
              (id) => !filters.some((filter) => filter.id === id)
            )
            if (missing)
              return resolve([
                400,
                { error: 'ERROR_DASHBOARD_FILTER_ORDER_INVALID' },
              ])
            filters = order.map((id) =>
              filters.find((filter) => filter.id === id)
            )
            resolve([204])
          }
        })
      })
      mock.onDelete('/dashboard/filters/6/').reply(() => {
        filters = filters.filter(({ id }) => id !== 6)
        return [204]
      })
      const wrapper = await testApp.mount(DashboardFilters, {
        global: { stubs: { Teleport: false } },
        props: { dashboard },
      })
      const controls = wrapper.findAll('.dashboard-filter')
      controls.forEach((control, index) => {
        control.element.getBoundingClientRect = () => ({
          left: index * 200,
          right: index * 200 + 180,
          top: 0,
          bottom: 60,
          width: 180,
          height: 60,
        })
      })
      await controls[2].get('.control__label').trigger('mousedown', {
        button: 0,
        clientX: 410,
        clientY: 10,
      })
      window.dispatchEvent(
        new MouseEvent('mousemove', { clientX: 0, clientY: 10, bubbles: true })
      )
      window.dispatchEvent(
        new MouseEvent('mouseup', { clientX: 0, clientY: 10, bubbles: true })
      )
      await flushPromises()
      expect(JSON.parse(mock.history.post[0].data)).toEqual({
        order: [7, 5, 6],
      })
      expect(labels(wrapper)).toEqual(['Region', 'Country', 'Channel'])
      for (const trigger of wrapper.findAll(
        '[aria-label="dashboardFilter.actions"]'
      )) {
        expect(trigger.element.disabled).toBe(true)
        await trigger.trigger('click')
      }
      expect(testApp.body.find('button:has(.iconoir-bin)').exists()).toBe(false)
      expect(mock.history.delete).toHaveLength(0)
      expect(wrapper.find('.dropdown__toggle-loading').exists()).toBe(false)
      expect(wrapper.find('.button-icon--loading').exists()).toBe(false)

      await store.dispatch('dashboardApplication/toggleEditMode')
      await wrapper.get('[aria-label="dashboardFilter.clear"]').trigger('click')
      await flushPromises()
      expect(mock.history.patch).toHaveLength(1)
      expect(JSON.parse(mock.history.patch[0].data)).toEqual({ values: [] })
      await store.dispatch('dashboardApplication/enterEditMode')

      finishOrder()
      await flushPromises()
      const channel = wrapper
        .findAll('.dashboard-filter')
        .find((control) => control.get('.control__label').text() === 'Channel')
      const trigger = channel.get('[aria-label="dashboardFilter.actions"]')
      expect(trigger.element.disabled).toBe(false)
      await trigger.trigger('click')
      await flushPromises()
      await testApp.body.get('button:has(.iconoir-bin)').trigger('click')
      await flushPromises()
      expect(mock.history.delete).toHaveLength(1)
      expect(labels(wrapper)).toEqual(
        failed ? ['Country', 'Region'] : ['Region', 'Country']
      )
    }
  )

  test.each(['view', 'permission', 'single'])(
    'disables dragging labels for %s',
    async (reason) => {
      if (reason === 'view')
        await store.dispatch('dashboardApplication/toggleEditMode')
      if (reason === 'permission')
        hasPermission.mockImplementation(
          (operation) => operation !== 'dashboard.order_filters'
        )
      if (reason === 'single') {
        filters = filters.slice(0, 1)
        await store.dispatch('dashboardApplication/fetchFilters')
      }
      const wrapper = await render()
      expect(wrapper.find('.dashboard-filter--movable').exists()).toBe(false)
    }
  )

  test.each([false, true])(
    'restores a failed move without overwriting a newer collection: %s',
    async (updated) => {
      testApp.dontFailOnErrorResponses()
      let finish
      mock.onPost('/dashboard/1/filters/order/').reply(
        () =>
          new Promise((resolve) => {
            finish = resolve
          })
      )
      const request = store.dispatch(
        'dashboardApplication/orderFilters',
        [6, 7, 5]
      )
      await vi.waitFor(() => expect(finish).toBeTypeOf('function'))
      expect(filterIds()).toEqual([6, 7, 5])
      if (updated) {
        filters = [filters[2], { ...filters[0], label: 'Updated country' }]
        await store.dispatch('dashboardApplication/fetchFilters')
      }
      finish([500])
      await expect(request).rejects.toThrow()
      expect(filterIds()).toEqual(updated ? [7, 5] : [5, 6, 7])
      expect(
        store.getters['dashboardApplication/getAppliedFilterValues'](5)
      ).toEqual(['France'])
    }
  )

  test('applies a remote reorder without reloading widget data or options', async () => {
    const handlers = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => {
        handlers[name] = handler
      },
    })
    filters = [filters[2], filters[0], filters[1]]
    await handlers.dashboard_filters_updated(
      { store },
      { dashboard_id: 1, order_only: true }
    )
    expect(filterIds()).toEqual([7, 5, 6])
    expect(mock.history.get.map(({ url }) => url)).toEqual([
      '/dashboard/1/filters/',
      '/dashboard/1/data-sources/',
    ])
    expect(mock.history.post).toHaveLength(0)
    expect(
      store.getters['dashboardApplication/getAppliedFilterValues'](5)
    ).toEqual(['France'])
  })

  test('does not change another dashboard after a delayed save', async () => {
    let finish
    mock.onPost('/dashboard/1/filters/order/').reply(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const request = store.dispatch(
      'dashboardApplication/orderFilters',
      [6, 7, 5]
    )
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'))
    mock.onGet('/dashboard/2/widgets/').reply(200, [])
    mock.onGet('/dashboard/2/data-sources/').reply(200, [])
    mock.onGet('/dashboard/2/filters/').reply(200, [])
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: 2,
      forEditing: false,
    })
    mock.resetHistory()
    finish([204])
    await request
    expect(filterIds()).toEqual([])
    expect(mock.history.get).toHaveLength(0)
  })
})
