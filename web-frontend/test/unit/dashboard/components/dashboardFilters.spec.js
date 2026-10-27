import { flushPromises } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardFilters from '@baserow/modules/dashboard/components/filter/DashboardFilters'
import DashboardSidebar from '@baserow/modules/dashboard/components/DashboardSidebar'
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

describe('shared dashboard filter selections', () => {
  let testApp, store, mock, filters
  const dashboard = { id: 1, workspace: { id: 1 } }

  beforeEach(async () => {
    hasPermission.mockReturnValue(true)
    testApp = new TestApp()
    store = testApp.store
    mock = testApp.mock
    filters = [
      {
        id: 5,
        dashboard_id: 1,
        label: 'Team',
        type: 'text',
        operator: 'equal',
        mode: 'dropdown',
        multiple: true,
        formula_value: { formula: 'Design,Sales', mode: 'simple' },
        values: ['Design'],
      },
    ]
    mock.onGet('/dashboard/1/widgets/').reply(200, [])
    mock.onGet('/dashboard/1/filters/').reply(() => [200, filters])
    mock.onGet('/dashboard/1/data-sources/').reply(200, [])
    mock.onPost('/dashboard/filters/5/options/').reply(200, {
      results: ['Design', 'Sales'],
      available: ['Design', 'Sales'],
      next: null,
    })
    mock.onPatch('/dashboard/filters/5/').reply(({ data }) => {
      filters = [{ ...filters[0], ...JSON.parse(data) }]
      return [200, filters[0]]
    })
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: dashboard.id,
      forEditing: false,
    })
    mock.resetHistory()
  })

  afterEach(() => testApp.afterEach())

  const render = () =>
    testApp.mount(DashboardFilters, {
      global: { stubs: { Teleport: false } },
      props: { dashboard },
    })

  async function selectSales(wrapper) {
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    await testApp.body.findAll('input[type="checkbox"]')[1].setValue(true)
    await testApp.body.get('form').trigger('submit')
    await flushPromises()
  }

  test.each([
    ['simple', "'France,Belgium'"],
    ['advanced', "'France,Belgium'"],
    ['simple', ''],
    ['advanced', ''],
  ])(
    'selects filters in edit mode without saving or fetching sources (%s, %s)',
    async (mode, secondFormula) => {
      filters = [
        {
          ...filters[0],
          formula_value: { formula: "'Design,Sales'", mode },
        },
        {
          ...filters[0],
          id: 6,
          label: 'Country',
          formula_value: { formula: secondFormula, mode },
          values: [],
        },
      ]
      mock.onPatch('/dashboard/filters/6/').reply(({ data }) => {
        filters[1] = { ...filters[1], ...JSON.parse(data) }
        return [200, filters[1]]
      })
      await store.dispatch('dashboardApplication/fetchFilters')
      await store.dispatch('dashboardApplication/enterEditMode')
      const wrapper = await testApp.mount(
        defineComponent({
          components: { DashboardFilters, DashboardSidebar },
          data: () => ({ dashboard }),
          template: `<div>
            <DashboardFilters :dashboard="dashboard" />
            <DashboardSidebar :dashboard="dashboard" />
          </div>`,
        }),
        { global: { stubs: { Teleport: false } } }
      )
      mock.resetHistory()

      for (const index of [0, 1, 0]) {
        await wrapper
          .findAll('.dashboard-filter .dropdown__selected')
          [index].trigger('click')
        await flushPromises()
        expect(
          wrapper.get('.dashboard-filter-settings input').element.value
        ).toBe(index === 0 ? 'Team' : 'Country')
        if (index === 1 && !secondFormula) {
          expect(
            wrapper.find('.formula-input-field--formula-empty').exists()
          ).toBe(true)
        } else {
          expect(wrapper.get('.formula-input-field').text()).toContain(
            index === 0 ? 'Design,Sales' : 'France,Belgium'
          )
        }
        expect(mock.history.patch).toHaveLength(0)
        expect(mock.history.get).toHaveLength(0)
        expect(mock.history.post).toHaveLength(0)
      }
    }
  )

  test('checks update permission on the filter and shows shared values read-only to viewers', async () => {
    hasPermission.mockImplementation(
      (operation) => operation !== 'dashboard.filter.update'
    )
    const wrapper = await render()
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
    expect(wrapper.get('.dropdown__selected').element.disabled).toBe(true)
    expect(wrapper.find('[aria-label="dashboardFilter.clear"]').exists()).toBe(
      false
    )
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    expect(mock.history.patch).toHaveLength(0)
    expect(hasPermission).toHaveBeenCalledWith(
      'dashboard.filter.update',
      filters[0],
      dashboard.workspace.id
    )
  })

  test('shows saving state and keeps the saved selection until the update succeeds', async () => {
    let finishSave
    mock.onPatch('/dashboard/filters/5/').reply(
      () =>
        new Promise((resolve) => {
          finishSave = () => {
            filters = [{ ...filters[0], values: ['Design', 'Sales'] }]
            resolve([200, filters[0]])
          }
        })
    )
    const wrapper = await render()
    await selectSales(wrapper)
    expect(mock.history.patch).toHaveLength(1)
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({
      values: ['Design', 'Sales'],
    })
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
    expect(wrapper.get('.dropdown__selected').element.disabled).toBe(true)
    expect(testApp.body.get('button[type="submit"]').classes()).toContain(
      'button--loading'
    )
    expect(wrapper.get('.dropdown__selected').attributes('aria-expanded')).toBe(
      'true'
    )
    const clear = wrapper.get('[aria-label="dashboardFilter.clear"]')
    expect(clear.element.disabled).toBe(true)
    await clear.trigger('click')
    expect(mock.history.patch).toHaveLength(1)
    finishSave()
    await flushPromises()
    expect(wrapper.get('.dashboard-filter__value').text()).toBe(
      'dashboardFilter.selections - 2'
    )
    expect(wrapper.get('.dropdown__selected').element.disabled).toBe(false)
    expect(wrapper.find('.dropdown__toggle-loading').exists()).toBe(false)
  })

  test('keeps the previous selection, reports a failed save and allows retrying', async () => {
    testApp.dontFailOnErrorResponses()
    mock.onPatch('/dashboard/filters/5/').reply(500)
    const wrapper = await render()
    const notifications = await testApp.mount(Toasts)
    await selectSales(wrapper)
    expect(wrapper.get('.dashboard-filter__value').text()).toBe('Design')
    expect(wrapper.get('.dropdown__selected').element.disabled).toBe(false)
    expect(notifications.find('.toast').exists()).toBe(true)
    expect(wrapper.get('.dropdown__selected').attributes('aria-expanded')).toBe(
      'true'
    )
    expect(
      testApp.body.findAll('input[type="checkbox"]')[1].element.checked
    ).toBe(true)
    mock.onPatch('/dashboard/filters/5/').reply(({ data }) => {
      filters = [{ ...filters[0], ...JSON.parse(data) }]
      return [200, filters[0]]
    })
    await testApp.body.get('form').trigger('submit')
    await flushPromises()
    expect(mock.history.patch).toHaveLength(2)
    expect(JSON.parse(mock.history.patch[1].data)).toEqual({
      values: ['Design', 'Sales'],
    })
    expect(wrapper.get('.dashboard-filter__value').text()).toBe(
      'dashboardFilter.selections - 2'
    )
  })

  test('keeps other filters usable while independent selections are saving', async () => {
    filters.push({
      ...filters[0],
      id: 6,
      label: 'Country',
      mode: 'input',
      values: ['France'],
    })
    await store.dispatch('dashboardApplication/fetchFilters')
    const saves = new Map()
    for (const id of [5, 6]) {
      mock.onPatch(`/dashboard/filters/${id}/`).reply(
        ({ data }) =>
          new Promise((resolve) => {
            saves.set(id, () => {
              filters = filters.map((filter) =>
                filter.id === id ? { ...filter, ...JSON.parse(data) } : filter
              )
              resolve([200, filters.find((filter) => filter.id === id)])
            })
          })
      )
    }
    const wrapper = await render()
    await selectSales(wrapper)
    const triggers = wrapper.findAll('.dropdown__selected')
    expect(triggers.map((trigger) => trigger.element.disabled)).toEqual([
      true,
      false,
    ])
    expect(wrapper.find('.dropdown__toggle-loading').exists()).toBe(false)
    expect(testApp.body.findAll('.button--loading')).toHaveLength(1)

    await triggers[1].trigger('click')
    await flushPromises()
    await testApp.body.get('.dashboard-filter__input input').setValue('Belgium')
    await testApp.body
      .get('form:has(.dashboard-filter__input)')
      .trigger('submit')
    await flushPromises()
    expect(saves.size).toBe(2)
    saves.get(5)()
    await flushPromises()
    expect(triggers.map((trigger) => trigger.element.disabled)).toEqual([
      false,
      true,
    ])
    saves.get(6)()
    await flushPromises()
    expect(triggers.map((trigger) => trigger.element.disabled)).toEqual([
      false,
      false,
    ])
    expect(
      wrapper.findAll('.dashboard-filter__value').map((value) => value.text())
    ).toEqual(['dashboardFilter.selections - 2', 'Belgium'])
  })

  test('persists clearing the selection', async () => {
    const wrapper = await render()
    await wrapper.get('[aria-label="dashboardFilter.clear"]').trigger('click')
    await flushPromises()
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({ values: [] })
    expect(wrapper.get('.dashboard-filter__value').text()).toBe(
      'dashboardFilter.choose'
    )
    expect(wrapper.find('[aria-label="dashboardFilter.clear"]').exists()).toBe(
      false
    )
  })

  test.each([
    ['text', 'Design', 'Marketing'],
    ['number', '10', '42'],
  ])('keeps a rejected %s input ready to retry', async (type, saved, draft) => {
    testApp.dontFailOnErrorResponses()
    filters = [{ ...filters[0], type, mode: 'input', values: [saved] }]
    await store.dispatch('dashboardApplication/fetchFilters')
    mock.onPatch('/dashboard/filters/5/').reply(500)
    const wrapper = await render()
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    const input = testApp.body.get('.dashboard-filter__input input')
    await input.setValue(draft)
    await testApp.body.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.dropdown__selected').attributes('aria-expanded')).toBe(
      'true'
    )
    expect(input.element.value).toBe(draft)
    expect(wrapper.get('.dashboard-filter__value').text()).toBe(saved)

    mock.onPatch('/dashboard/filters/5/').reply(({ data }) => {
      filters = [{ ...filters[0], ...JSON.parse(data) }]
      return [200, filters[0]]
    })
    await testApp.body.get('form').trigger('submit')
    await flushPromises()
    expect(mock.history.patch.map(({ data }) => JSON.parse(data))).toEqual([
      { values: [draft] },
      { values: [draft] },
    ])
    expect(wrapper.get('.dashboard-filter__value').text()).toBe(draft)
    expect(wrapper.get('.dropdown__selected').attributes('aria-expanded')).toBe(
      'false'
    )
  })

  test('duplicates the persisted selection along with the filter configuration', async () => {
    mock.onPost('/dashboard/1/filters/').reply(({ data }) => {
      const created = { id: 6, dashboard_id: 1, ...JSON.parse(data) }
      filters = [...filters, created]
      return [200, created]
    })
    await store.dispatch('dashboardApplication/enterEditMode')
    const wrapper = await render()
    await wrapper.get('[aria-label="dashboardFilter.actions"]').trigger('click')
    await flushPromises()
    await testApp.body.get('button:has(.iconoir-copy)').trigger('click')
    await flushPromises()
    const request = mock.history.post.find(
      ({ url }) => url === '/dashboard/1/filters/'
    )
    expect(JSON.parse(request.data)).toEqual({
      label: 'Team 1',
      type: 'text',
      operator: 'equal',
      mode: 'dropdown',
      multiple: true,
      formula_value: { formula: 'Design,Sales', mode: 'simple' },
      values: ['Design'],
    })
    expect(
      wrapper.findAll('.dashboard-filter__value').map((value) => value.text())
    ).toEqual(['Design', 'Design'])
  })
})
