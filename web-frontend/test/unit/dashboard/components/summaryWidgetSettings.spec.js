import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import WidgetSettings from '@baserow/modules/dashboard/components/widget/WidgetSettings'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

test('summary sources expose the shared filter control and save permanent conditions', async () => {
  const source = {
    id: 4,
    integration_id: 10,
    table_id: 2,
    field_id: 3,
    aggregation_type: 'sum',
    view_id: null,
    filters: [],
    filter_groups: [],
    filter_type: 'AND',
  }
  const widget = {
    id: 5,
    type: 'summary',
    title: 'Total',
    description: '',
    data_source_id: 4,
  }
  const store = testApp.store
  store.commit('dashboardApplication/SET_DASHBOARD_ID', 1)
  store.commit('dashboardApplication/SET_DATA_SOURCES', [source])
  store.commit('dashboardApplication/SET_WIDGETS', [widget])
  vi.spyOn(store.$client, 'get').mockResolvedValue({
    data: [
      { id: 7, name: 'Name', type: 'text', table_id: 2 },
      {
        id: 3,
        name: 'Amount',
        type: 'number',
        table_id: 2,
        number_decimal_places: 0,
      },
    ],
  })
  const dispatch = vi.spyOn(store, 'dispatch').mockResolvedValue()
  const wrapper = await testApp.mount(WidgetSettings, {
    props: { dashboard: { id: 1 }, widget },
    global: { stubs: { Teleport: false } },
  })
  await flushPromises()
  // Integration metadata can arrive after widgets and data sources.
  store.commit('dashboardApplication/ADD_INTEGRATION', {
    id: 10,
    context_data: {
      databases: [
        {
          id: 1,
          name: 'Database',
          tables: [{ id: 2, name: 'Rows' }],
          views: [],
        },
      ],
    },
  })
  await flushPromises()
  expect(wrapper.html()).toMatchSnapshot()
  const filterButton = wrapper.find(
    '.service-form__filter-buttons .header__filter-link'
  )
  expect(filterButton.text()).toBe('serviceRefinementForms.filterTabTitle - 0')
  await filterButton.trigger('click')
  const body = new DOMWrapper(document.body)
  const context = body.find('.service-form__context--filter')
  expect(context.text()).toContain(
    'localBaserowTableServiceConditionalForm.noFilterTitle'
  )
  await context
    .findAll('button')
    .find(
      (button) =>
        button.text() === 'localBaserowTableServiceConditionalForm.addFilter'
    )
    .trigger('click')
  await flushPromises()
  const valueInput = context.find(
    'input[placeholder="localBaserowTableServiceConditionalForm.textFilterInputPlaceholder"]'
  )
  await valueInput.setValue('Alpha')
  await valueInput.trigger('keydown', { key: 'Enter' })
  await flushPromises()
  expect(dispatch).toHaveBeenCalledWith(
    'dashboardApplication/updateDataSource',
    {
      dataSourceId: 4,
      values: expect.objectContaining({
        filters: [
          expect.objectContaining({
            field: 7,
            type: 'equal',
            value: expect.objectContaining({ formula: 'Alpha', mode: 'raw' }),
          }),
        ],
      }),
    }
  )
  expect(context.find('[contenteditable=true]').exists()).toBe(false)
})
