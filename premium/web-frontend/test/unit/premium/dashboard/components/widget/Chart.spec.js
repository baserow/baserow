import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import Chart from '@baserow_premium/dashboard/components/widget/Chart'

describe('Premium dashboard Chart component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = async ({
    dataSourceData,
    dataSource = {},
    seriesConfig = [{ series_id: 1, series_chart_type: 'BAR' }],
  }) => {
    return await testApp.mount(Chart, {
      props: {
        dataSource: {
          type: 'local_baserow_grouped_aggregate_rows',
          aggregation_series: [
            { id: 1, field_id: 10, aggregation_type: 'sum' },
          ],
          aggregation_group_bys: [],
          schema: {
            items: {
              properties: {
                field_10_sum: {
                  title: 'Amount sum',
                  metadata: {
                    display_name: 'Amount sum',
                    source_field: {
                      display_name: 'Amount',
                    },
                    aggregation: {
                      type: 'sum',
                    },
                  },
                },
              },
            },
          },
          context_data: {
            fields: {},
          },
          ...dataSource,
        },
        dataSourceData,
        seriesConfig,
      },
      global: {
        stubs: {
          Bar: {
            name: 'Bar',
            props: ['data', 'options'],
            template: '<div class="bar-chart"></div>',
          },
          Pie: {
            name: 'Pie',
            props: ['data', 'options'],
            template: '<div class="pie-chart"></div>',
          },
        },
      },
    })
  }

  test('renders chart data from grouped aggregation results', async () => {
    const wrapper = await mountComponent({
      dataSourceData: {
        results: [
          {
            'Amount sum': 20,
          },
        ],
      },
    })

    expect(wrapper.find('.chart__no-data').exists()).toBe(false)
    const chartData = wrapper.findComponent({ name: 'Bar' }).props('data')
    expect(chartData.labels).toEqual([''])
    expect(chartData.datasets[0].type).toBe('bar')
    expect(chartData.datasets[0].data).toEqual([20])
    expect(chartData.datasets[0].label).toBe('Amount (viewAggregationType.sum)')
  })

  test('renders chart data using source field metadata from result fields', async () => {
    const wrapper = await mountComponent({
      dataSource: {
        schema: {
          items: {
            properties: {
              field_10_sum: {
                title: 'Amount sum',
                metadata: {
                  display_name: 'Amount sum',
                  source_field: {
                    display_name: 'Amount',
                  },
                  aggregation: {
                    type: 'sum',
                  },
                },
              },
            },
          },
        },
      },
      dataSourceData: {
        results: [
          {
            'Amount sum': 20,
          },
        ],
      },
    })

    expect(wrapper.find('.chart__no-data').exists()).toBe(false)
    const chartData = wrapper.findComponent({ name: 'Bar' }).props('data')
    expect(chartData.labels).toEqual([''])
    expect(chartData.datasets[0].type).toBe('bar')
    expect(chartData.datasets[0].data).toEqual([20])
    expect(chartData.datasets[0].label).toBe('Amount (viewAggregationType.sum)')
  })

  test('renders chart label from schema property display name when source field metadata is missing', async () => {
    const wrapper = await mountComponent({
      dataSource: {
        schema: {
          items: {
            properties: {
              field_10_sum: {
                title: 'Amount total',
                metadata: {
                  display_name: 'Amount total',
                },
              },
            },
          },
        },
      },
      dataSourceData: {
        results: [
          {
            'Amount total': 20,
          },
        ],
      },
    })

    const chartData = wrapper.findComponent({ name: 'Bar' }).props('data')
    expect(chartData.datasets[0].label).toBe(
      'Amount total (viewAggregationType.sum)'
    )
  })

  test('renders no-grouping chart data as a single-row list when group config is missing', async () => {
    const wrapper = await mountComponent({
      dataSource: {
        aggregation_group_bys: undefined,
      },
      dataSourceData: {
        results: [
          {
            'Amount sum': 20,
          },
        ],
      },
    })

    expect(wrapper.find('.chart__no-data').exists()).toBe(false)
    const chartData = wrapper.findComponent({ name: 'Bar' }).props('data')
    expect(chartData.labels).toEqual([''])
    expect(chartData.datasets[0].type).toBe('bar')
    expect(chartData.datasets[0].data).toEqual([20])
  })

  test('renders no-grouping pie chart data as series slices', async () => {
    const wrapper = await mountComponent({
      dataSource: {
        aggregation_series: [
          { id: 1, field_id: 10, aggregation_type: 'sum' },
          { id: 2, field_id: 12, aggregation_type: 'sum' },
        ],
        aggregation_group_bys: [],
        schema: {
          items: {
            properties: {
              field_10_sum: {
                title: 'Amount sum',
                metadata: {
                  display_name: 'Amount sum',
                  source_field: {
                    display_name: 'Amount',
                  },
                  aggregation: {
                    type: 'sum',
                  },
                },
              },
              field_12_sum: {
                title: 'Revenue sum',
                metadata: {
                  display_name: 'Revenue sum',
                  source_field: {
                    display_name: 'Revenue',
                  },
                  aggregation: {
                    type: 'sum',
                  },
                },
              },
            },
          },
        },
      },
      dataSourceData: {
        results: [
          {
            'Amount sum': 20,
            'Revenue sum': 10,
          },
        ],
      },
      seriesConfig: [
        { series_id: 1, series_chart_type: 'PIE' },
        { series_id: 2, series_chart_type: 'PIE' },
      ],
    })

    const chartData = wrapper.findComponent({ name: 'Pie' }).props('data')
    expect(chartData.labels).toEqual([
      'Amount (viewAggregationType.sum)',
      'Revenue (viewAggregationType.sum)',
    ])
    expect(chartData.datasets).toHaveLength(1)
    expect(chartData.datasets[0].data).toEqual([20, 10])
    expect(chartData.datasets[0].backgroundColor).toBeInstanceOf(Array)
  })

  test('renders grouped chart data from human result property names', async () => {
    const wrapper = await mountComponent({
      dataSource: {
        aggregation_group_bys: [{ field_id: 11 }],
        schema: {
          items: {
            properties: {
              field_10_sum: {
                title: 'Amount sum',
                metadata: {
                  display_name: 'Amount sum',
                  source_field: {
                    display_name: 'Amount',
                  },
                  aggregation: {
                    type: 'sum',
                  },
                },
              },
              field_11: {
                title: 'Category',
                metadata: {
                  id: 11,
                  type: 'text',
                },
              },
            },
          },
        },
        context_data: {
          fields: {
            field_11: {
              type: 'text',
            },
          },
        },
      },
      dataSourceData: {
        results: [
          {
            'Amount sum': 20,
            Category: 'Hardware',
          },
        ],
      },
    })

    const chartData = wrapper.findComponent({ name: 'Bar' }).props('data')
    expect(chartData.labels).toEqual(['Hardware'])
    expect(chartData.datasets[0].data).toEqual([20])
  })

  test('renders grouped single select labels from human result property names', async () => {
    const wrapper = await mountComponent({
      dataSource: {
        aggregation_group_bys: [{ field_id: 11 }],
        schema: {
          items: {
            properties: {
              field_10_sum: {
                title: 'Amount sum',
                metadata: {
                  display_name: 'Amount sum',
                  source_field: {
                    display_name: 'Amount',
                  },
                  aggregation: {
                    type: 'sum',
                  },
                },
              },
              field_11: {
                title: 'Category',
                metadata: {
                  id: 11,
                  type: 'single_select',
                },
              },
            },
          },
        },
        context_data: {
          fields: {
            field_11: {
              type: 'single_select',
              select_options: [
                { id: 1, value: 'Hardware', color: 'red' },
                { id: 2, value: 'Software', color: 'blue' },
              ],
            },
          },
        },
      },
      dataSourceData: {
        results: [
          {
            'Amount sum': 20,
            Category: { id: 1, value: 'Hardware', color: 'red' },
          },
          {
            'Amount sum': 10,
            Category: { id: 2, value: 'Software', color: 'blue' },
          },
        ],
      },
    })

    const chartData = wrapper.findComponent({ name: 'Bar' }).props('data')
    expect(chartData.labels).toEqual(['Hardware', 'Software'])
    expect(chartData.datasets[0].data).toEqual([20, 10])
  })

  test('renders chart data from technical result property names as a fallback', async () => {
    const wrapper = await mountComponent({
      dataSourceData: {
        results: [
          {
            field_10_sum: 20,
          },
        ],
      },
    })

    const chartData = wrapper.findComponent({ name: 'Bar' }).props('data')
    expect(chartData.datasets[0].data).toEqual([20])
  })

  test('renders grouped labels from technical group-by property names as a fallback', async () => {
    const wrapper = await mountComponent({
      dataSource: {
        aggregation_group_bys: [{ field_id: 11 }],
        schema: {
          items: {
            properties: {
              field_10_sum: {
                title: 'Amount sum',
                metadata: {
                  display_name: 'Amount sum',
                  source_field: {
                    display_name: 'Amount',
                  },
                  aggregation: {
                    type: 'sum',
                  },
                },
              },
              field_11: {
                title: 'Category',
                metadata: {
                  id: 11,
                  type: 'text',
                },
              },
              field_12: {
                title: 'Name',
                metadata: {
                  id: 12,
                  type: 'text',
                  primary: true,
                },
              },
            },
          },
        },
        context_data: {
          fields: {
            field_11: {
              type: 'text',
            },
            field_12: {
              type: 'text',
            },
          },
        },
      },
      dataSourceData: {
        results: [
          {
            'Amount sum': 20,
            field_11: 'Hardware',
            Name: 'OTHER_VALUES',
          },
        ],
      },
    })

    const chartData = wrapper.findComponent({ name: 'Bar' }).props('data')
    expect(chartData.labels).toEqual(['Hardware'])
    expect(chartData.datasets[0].data).toEqual([20])
  })
})
