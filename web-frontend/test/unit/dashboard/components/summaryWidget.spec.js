import { TestApp } from '@baserow/test/helpers/testApp'
import { nextTick } from 'vue'
import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'
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

test('shows no number before its data source and data are known', async () => {
  const wrapper = await testApp.mount(SummaryWidget, {
    props: { widget: { id: 5, type: 'summary', data_source_id: 4 } },
  })
  expect(wrapper.find('.dashboard-summary-widget__summary').text()).toBe('')
})

/** Exercise retained results through the dashboard wrapper and real summary content. */
test('keeps the previous summary visible during refresh, then displays an empty result', async () => {
  const store = testApp.store
  const source = {
    id: 4,
    type: 'local_baserow_aggregate_rows',
    aggregation_type: 'sum',
    context_data: {
      field: {
        id: 3,
        type: 'number',
        number_decimal_places: 0,
        number_separator: '',
        number_prefix: '',
        number_suffix: '',
      },
    },
  }
  store.commit('dashboardApplication/SET_DATA_SOURCES', [source])
  const setData = (values) =>
    store.commit('dashboardApplication/UPDATE_DATA', {
      dataSourceId: 4,
      values,
    })
  setData({ result: 42, _loaded: true })
  const wrapper = await testApp.mount(DashboardWidget, {
    props: {
      dashboard: { workspace: { id: 1 } },
      widget: { id: 5, type: 'summary', data_source_id: 4, title: 'Count' },
    },
  })
  const summary = wrapper.get('.dashboard-summary-widget__summary')
  setData({ result: 42, _loaded: true, _loading: true })
  await nextTick()
  expect(summary.text()).toBe('42')
  expect(wrapper.get('.dashboard-summary-widget__summary').element).toBe(
    summary.element
  )
  expect(wrapper.find('.skeleton-loading').exists()).toBe(false)
  expect(wrapper.find('[role="status"]').exists()).toBe(true)
  setData({ result: null, _loaded: true })
  await nextTick()
  expect(summary.text()).toBe('0')
  expect(wrapper.find('[role="status"]').exists()).toBe(false)
})
