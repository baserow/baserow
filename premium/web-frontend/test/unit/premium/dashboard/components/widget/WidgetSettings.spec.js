import flushPromises from 'flush-promises'
import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import WidgetSettings from '@baserow/modules/dashboard/components/widget/WidgetSettings'

describe.each(['chart', 'pie_chart'])('%s filter settings', (type) => {
  let testApp
  let savedDataSource
  const widget = {
    id: 10,
    type,
    title: 'Chart',
    description: '',
    data_source_id: 12,
    series_config: [
      { series_id: 7, series_chart_type: 'bar', series_color: '#000000' },
    ],
  }

  beforeEach(() => {
    testApp = new PremiumTestApp()
    savedDataSource = {
      id: 12,
      type: 'local_baserow_grouped_aggregate_rows',
      integration_id: 3,
      table_id: 4,
      view_id: null,
      filters: [
        {
          id: 1,
          field: 5,
          type: 'equal',
          value: { formula: 'Before', mode: 'raw' },
        },
      ],
      filter_type: 'AND',
      aggregation_series: [{ id: 7, field_id: 5, aggregation_type: 'count' }],
      aggregation_group_bys: [],
      aggregation_sorts: [],
    }
    testApp.store.commit(
      'dashboardApplication/ADD_DATA_SOURCE',
      structuredClone(savedDataSource)
    )
    testApp.store.commit('dashboardApplication/ADD_INTEGRATION', {
      id: 3,
      context_data: {
        databases: [
          {
            id: 2,
            name: 'Database',
            tables: [{ id: 4, name: 'Table' }],
            views: [],
          },
        ],
      },
    })
    testApp.mock
      .onGet('/database/fields/table/4/')
      .reply(200, [{ id: 5, name: 'Name', type: 'text', primary: true }])
    testApp.mock.onPatch('/dashboard/data-sources/12/').reply(({ data }) => {
      savedDataSource = { ...savedDataSource, ...JSON.parse(data) }
      return [200, savedDataSource]
    })
    testApp.mock
      .onPost('/dashboard/data-sources/12/dispatch/')
      .reply(200, { results: [] })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  /** Mount the real settings and open the chart's filter popover. */
  async function openFilters() {
    const wrapper = await testApp.mount(WidgetSettings, {
      props: { dashboard: { id: 1, workspace: { id: 1 } }, widget },
    })
    await flushPromises()
    await wrapper.find('.iconoir-filter').element.parentElement.click()
    await flushPromises()
    return wrapper
  }

  test('edits a filter value and restores the saved value on reload', async () => {
    const wrapper = await openFilters()
    const input = wrapper.find('.filters__value--formula-input input')
    expect(input.element.value).toBe('Before')
    await input.setValue('42')
    await input.trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => {
      expect(savedDataSource.filters[0].value.formula).toBe('42')
    })
    expect(savedDataSource.filters).toMatchInlineSnapshot(`
      [
        {
          "field": 5,
          "id": 1,
          "type": "equal",
          "value": {
            "formula": "42",
            "mode": "raw",
          },
        },
      ]
    `)
    await flushPromises()
    wrapper.unmount()

    testApp.store.commit('dashboardApplication/UPDATE_DATA_SOURCE', {
      dataSourceId: 12,
      values: structuredClone(savedDataSource),
    })
    const reloaded = await openFilters()
    expect(
      reloaded.find('.filters__value--formula-input input').element.value
    ).toBe('42')
    await reloaded.find('.formula-input-field__mode-toggle').trigger('click')
    expect(reloaded.find('.tiptap').text()).toContain('42')
    await flushPromises()
    expect(savedDataSource.filters[0].value.mode).toBe('simple')
  })
})
