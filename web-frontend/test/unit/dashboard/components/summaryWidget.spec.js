import { TestApp } from '@baserow/test/helpers/testApp'
import SummaryWidget from '@baserow/modules/dashboard/components/widget/SummaryWidget'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

test.each([
  ['sum', null, '$0.00'],
  ['sum', 0, '$0.00'],
  ['sum', '0', '$0.00'],
  ['sum', '12.5', '$12.50'],
  ['average', null, ''],
])(
  'renders %s result %s with field formatting',
  async (aggregation_type, result, expected) => {
    const source = {
      id: 4,
      type: 'local_baserow_aggregate_rows',
      aggregation_type,
      context_data: {
        field: {
          id: 3,
          type: 'number',
          number_decimal_places: 2,
          number_separator: '',
          number_prefix: '$',
          number_suffix: '',
        },
      },
    }
    testApp.store.commit('dashboardApplication/SET_DATA_SOURCES', [source])
    testApp.store.commit('dashboardApplication/UPDATE_DATA', {
      dataSourceId: 4,
      values: { result },
    })
    const wrapper = await testApp.mount(SummaryWidget, {
      props: { widget: { id: 5, type: 'summary', data_source_id: 4 } },
    })
    expect(wrapper.find('.dashboard-summary-widget__summary').text()).toBe(
      expected
    )
    expect(wrapper.html()).toMatchSnapshot()
    expect(testApp.store.state.dashboardApplication.data[4].result).toBe(result)
  }
)
