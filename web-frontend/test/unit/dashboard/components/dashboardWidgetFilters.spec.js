import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'

describe('widget filter indicator', () => {
  let testApp, store
  const dashboard = { id: 1, workspace: { id: 1 } }
  const widget = {
    id: 2,
    type: 'summary',
    title: 'Revenue',
    data_source_id: 10,
  }
  const filter = {
    id: 5,
    label: 'Country',
    type: 'text',
    operator: 'equal',
    mode: 'input',
    multiple: false,
  }
  const condition = {
    field: 20,
    type: 'equal',
    value: { formula: "get('dashboard_filter.5')", mode: 'simple' },
  }

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    testApp.mock.onGet('/dashboard/1/widgets/').reply(200, [widget])
    let savedFilter = { ...filter, values: [] }
    testApp.mock
      .onGet('/dashboard/1/filters/')
      .reply(() => [200, [savedFilter]])
    testApp.mock.onPatch('/dashboard/filters/5/').reply(({ data }) => {
      savedFilter = { ...savedFilter, ...JSON.parse(data) }
      return [200, savedFilter]
    })
    testApp.mock.onGet('/dashboard/1/data-sources/').reply(200, [
      { id: 10, type: 'local_baserow_aggregate_rows', filters: [condition] },
      { id: 11, type: 'local_baserow_aggregate_rows', filters: [] },
    ])
    testApp.mock
      .onPost(/\/dashboard\/data-sources\/1[01]\/dispatch\//)
      .reply(200, { result: 42 })
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: 1,
      forEditing: false,
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const apply = (values) =>
    store.dispatch('dashboardApplication/applyFilter', { filterId: 5, values })

  const render = (values = widget) =>
    testApp.mount(DashboardWidget, {
      props: { dashboard, widget: values },
      global: { stubs: { SummaryWidget: true } },
    })

  test('shows the icon beside the title only after applying a linked filter', async () => {
    const wrapper = await render()
    const indicator = '.dashboard-widget__filter-status'
    expect(wrapper.find(indicator).exists()).toBe(false)

    await apply(['France'])
    const status = wrapper.get(indicator)
    expect(status.get('.iconoir-filter').exists()).toBe(true)
    expect(status.element.previousElementSibling.textContent).toBe('Revenue')
    expect(status.attributes('aria-label')).toBe('widget.filtered')
    expect(status.attributes('tabindex')).toBe('0')

    await status.trigger('mouseenter')
    expect(testApp.body.get('.tooltip__content').text()).toBe('widget.filtered')
    await status.trigger('mouseleave')
    await status.trigger('focus')
    expect(testApp.body.get('.tooltip__content').text()).toBe('widget.filtered')

    await apply([])
    expect(wrapper.find(indicator).exists()).toBe(false)
    expect(testApp.body.find('.tooltip__content').exists()).toBe(false)
  })

  test('does not mark a widget whose source does not use the active filter', async () => {
    const wrapper = await render({ ...widget, data_source_id: 11 })
    await apply(['France'])
    expect(wrapper.find('.dashboard-widget__filter-status').exists()).toBe(
      false
    )
  })

  test.each([
    {
      name: 'a raw value',
      filters: [{ ...condition, value: { formula: 'France', mode: 'raw' } }],
    },
    {
      name: 'a formula literal',
      filters: [
        { ...condition, value: { formula: "'France'", mode: 'simple' } },
      ],
    },
    {
      name: 'an empty operator without a value',
      filters: [
        { ...condition, type: 'empty', value: { formula: '', mode: 'raw' } },
      ],
    },
    {
      name: 'a not empty operator without a value',
      filters: [
        {
          ...condition,
          type: 'not_empty',
          value: { formula: '', mode: 'raw' },
        },
      ],
    },
    {
      name: 'an even and whole operator without a value',
      filters: [
        {
          ...condition,
          type: 'is_even_and_whole',
          value: { formula: '', mode: 'raw' },
        },
      ],
    },
    ...['date_equals_today', 'date_before_today', 'date_after_today'].map(
      (type) => ({
        name: `a ${type} operator without a value`,
        filters: [{ ...condition, type, value: { formula: '', mode: 'raw' } }],
      })
    ),
    {
      name: 'a condition in a nested group',
      filters: [
        {
          ...condition,
          group: '31',
          value: { formula: 'France', mode: 'raw' },
        },
      ],
      filter_groups: [
        { id: '30', parent_group: null, filter_type: 'AND' },
        { id: '31', parent_group: '30', filter_type: 'OR' },
      ],
    },
    {
      name: 'an ordinary condition alongside an inactive dashboard link',
      filters: [
        condition,
        { ...condition, field: 21, value: { formula: 'Paid', mode: 'raw' } },
      ],
    },
    {
      name: 'a composed formula using an inactive dashboard link',
      filters: [
        {
          ...condition,
          value: {
            formula: "concat(get('dashboard_filter.5'), 'France')",
            mode: 'simple',
          },
        },
      ],
    },
  ])(
    'marks a widget filtered by $name without a dashboard selection',
    async ({ filters, filter_groups = [] }) => {
      testApp.mock.onGet('/dashboard/1/data-sources/').reply(200, [
        {
          id: 10,
          type: 'local_baserow_aggregate_rows',
          filters,
          filter_groups,
        },
      ])
      await store.dispatch('dashboardApplication/fetchNewDataSources', 1)

      const wrapper = await render()
      expect(
        wrapper.get('.dashboard-widget__filter-status .iconoir-filter').exists()
      ).toBe(true)
    }
  )

  test.each([
    { name: 'has no field yet', field: null },
    { name: 'references a trashed field', field: 20, trashed: true },
    {
      name: 'has an unfinished raw value',
      value: { formula: '', mode: 'raw' },
    },
    {
      name: 'has an unfinished simple formula',
      value: { formula: '', mode: 'simple' },
    },
    {
      name: 'has only whitespace in its raw value',
      value: { formula: '   ', mode: 'raw' },
    },
    {
      name: 'has only whitespace in its simple formula',
      value: { formula: '   ', mode: 'simple' },
    },
  ])(
    'does not mark a widget when its only condition $name',
    async ({
      field = 20,
      trashed = false,
      value = { formula: 'France', mode: 'raw' },
    }) => {
      testApp.mock.onGet('/dashboard/1/data-sources/').reply(200, [
        {
          id: 10,
          type: 'local_baserow_aggregate_rows',
          filters: [
            {
              ...condition,
              field,
              trashed,
              value,
            },
          ],
        },
      ])
      await store.dispatch('dashboardApplication/fetchNewDataSources', 1)

      const wrapper = await render()
      expect(wrapper.find('.dashboard-widget__filter-status').exists()).toBe(
        false
      )
    }
  )

  test('updates the indicator when a source condition is added and removed', async () => {
    const wrapper = await render({ ...widget, data_source_id: 11 })
    const indicator = '.dashboard-widget__filter-status'
    expect(wrapper.find(indicator).exists()).toBe(false)
    testApp.mock.onPatch('/dashboard/data-sources/11/').reply(({ data }) => [
      200,
      {
        id: 11,
        type: 'local_baserow_aggregate_rows',
        ...JSON.parse(data),
      },
    ])

    await store.dispatch('dashboardApplication/updateDataSource', {
      dataSourceId: 11,
      values: {
        filters: [{ ...condition, value: { formula: 'France', mode: 'raw' } }],
      },
    })
    expect(wrapper.get(indicator).attributes('aria-label')).toBe(
      'widget.filtered'
    )

    await store.dispatch('dashboardApplication/updateDataSource', {
      dataSourceId: 11,
      values: { filters: [] },
    })
    expect(wrapper.find(indicator).exists()).toBe(false)
  })

  test('removes the indicator when the control is deleted', async () => {
    const wrapper = await render()
    await apply(['France'])
    expect(wrapper.find('.dashboard-widget__filter-status').exists()).toBe(true)
    testApp.mock.onGet('/dashboard/1/filters/').reply(200, [])
    await store.dispatch('dashboardApplication/handleFiltersUpdated')
    expect(wrapper.find('.dashboard-widget__filter-status').exists()).toBe(
      false
    )
  })
})
