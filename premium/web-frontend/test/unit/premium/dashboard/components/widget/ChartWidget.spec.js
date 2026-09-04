import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import ChartWidget from '@baserow_premium/dashboard/components/widget/ChartWidget'
import PieChartWidget from '@baserow_premium/dashboard/components/widget/PieChartWidget'

describe.each([
  { name: 'ChartWidget', Component: ChartWidget },
  { name: 'PieChartWidget', Component: PieChartWidget },
])('Premium dashboard $name component', ({ Component }) => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const seedDataSource = () => {
    testApp.store.commit('dashboardApplication/ADD_DATA_SOURCE', {
      id: 12,
      type: 'local_baserow_grouped_aggregate_rows',
    })
    testApp.store.commit('dashboardApplication/UPDATE_DATA', {
      dataSourceId: 12,
      values: {
        results: [{ result: 1 }],
      },
    })
  }

  const mountComponent = async () => {
    seedDataSource()

    return await testApp.mount(Component, {
      props: {
        dashboard: {
          workspace: {
            id: 1,
          },
        },
        widget: {
          id: 10,
          title: 'Chart',
          data_source_id: 12,
          series_config: [],
        },
      },
      global: {
        stubs: {
          Chart: {
            name: 'Chart',
            emits: ['rendered'],
            template:
              '<div class="chart-stub" @click="$emit(\'rendered\')"></div>',
          },
        },
      },
    })
  }

  test('shows chart area loading spinner until chart has rendered', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.find('.dashboard-chart-widget__loading').exists()).toBe(
      false
    )
    expect(
      wrapper.find('.dashboard-chart-widget__content.loading-spinner').exists()
    ).toBe(true)
    expect(
      wrapper.find('.dashboard-chart-widget__chart--hidden').exists()
    ).toBe(true)

    await wrapper.find('.chart-stub').trigger('click')

    expect(
      wrapper.find('.dashboard-chart-widget__content.loading-spinner').exists()
    ).toBe(false)
    expect(
      wrapper.find('.dashboard-chart-widget__chart--hidden').exists()
    ).toBe(false)
  })
})
