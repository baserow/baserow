import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import WidgetSettings from '@baserow/modules/dashboard/components/widget/WidgetSettings'

describe('summary filter settings', () => {
  let testApp
  let savedDataSource
  const widget = {
    id: 10,
    type: 'summary',
    title: 'Orders',
    description: '',
    data_source_id: 12,
  }

  beforeEach(() => {
    testApp = new TestApp()
    savedDataSource = {
      id: 12,
      type: 'local_baserow_aggregate_rows',
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
      field_id: 5,
      aggregation_type: 'count',
      filter_groups: [],
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
      .reply(200, { result: 42 })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  /** Mount the real summary settings and open its source conditions. */
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

  test('renders dashboard filter values in source conditions', async () => {
    testApp.store.commit('dashboardApplication/SET_FILTERS', [
      { id: 7, label: 'Country', mode: 'input' },
    ])
    savedDataSource.filters[0].value = {
      formula: "get('dashboard_filter.7')",
      mode: 'simple',
    }
    testApp.store.commit('dashboardApplication/UPDATE_DATA_SOURCE', {
      dataSourceId: 12,
      values: structuredClone(savedDataSource),
    })
    const wrapper = await openFilters()
    expect(wrapper.get('.get-formula-component').text()).toContain('Country')
    expect(wrapper.find('.formula-input-field--error').exists()).toBe(false)
  })

  test('saves a condition group through the shared source editor', async () => {
    const wrapper = await openFilters()
    const addGroup = wrapper
      .findAll('.filters__add')
      .find(
        (item) =>
          item.text() ===
          'localBaserowTableServiceConditionalForm.addFilterGroup'
      )
    await addGroup.trigger('click')
    await vi.waitFor(() => {
      expect(savedDataSource.filter_groups).toHaveLength(1)
      expect(savedDataSource.filters).toHaveLength(2)
      expect(savedDataSource.filters[1].group).toBe(
        savedDataSource.filter_groups[0].id
      )
    })
  })
})
