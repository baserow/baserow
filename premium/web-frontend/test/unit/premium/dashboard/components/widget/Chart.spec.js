import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import Chart from '@baserow_premium/dashboard/components/widget/Chart'
import { getDashboardChartData } from '@baserow_premium/dashboard/chartData'

describe('Premium dashboard Chart component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const dataSource = (overrides = {}) => ({
    type: 'local_baserow_grouped_aggregate_rows',
    aggregation_series: [{ id: 1, field_id: 10, aggregation_type: 'sum' }],
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
    ...overrides,
  })

  const chartData = ({
    source = dataSource(),
    data = {},
    seriesConfig = [{ series_id: 1, series_chart_type: 'BAR' }],
  } = {}) => {
    return getDashboardChartData({
      dataSource: source,
      dataSourceData: {
        results: [
          {
            field_10_sum: 20,
          },
        ],
        ...data,
      },
      seriesConfig,
      $registry: testApp.$registry,
      $t: (key) => key,
    })
  }

  const mountComponent = async ({ data, options = null }) => {
    return await testApp.mount(Chart, {
      props: {
        data,
        options,
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

  test('builds chart data from grouped aggregation results', async () => {
    const data = chartData({
      data: {
        results: [
          {
            'Amount sum': 20,
          },
        ],
      },
    })

    expect(data.labels).toEqual([''])
    expect(data.datasets[0].type).toBe('bar')
    expect(data.datasets[0].data).toEqual([20])
    expect(data.datasets[0].label).toBe('Amount (viewAggregationType.sum)')
  })

  test('builds chart data when the grouped aggregation schema only exposes result fields', async () => {
    const data = chartData({
      source: dataSource({
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
      }),
      data: {
        results: [
          {
            'Amount sum': 20,
          },
        ],
      },
    })

    expect(data.labels).toEqual([''])
    expect(data.datasets[0].type).toBe('bar')
    expect(data.datasets[0].data).toEqual([20])
    expect(data.datasets[0].label).toBe('Amount (viewAggregationType.sum)')
  })

  test('builds chart label from schema property display name when source field metadata is missing', async () => {
    const data = chartData({
      source: dataSource({
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
      }),
      data: {
        results: [
          {
            'Amount total': 20,
          },
        ],
      },
    })

    expect(data.datasets[0].label).toBe(
      'Amount total (viewAggregationType.sum)'
    )
  })

  test('builds no-grouping chart data as a single-row list when group config is missing', async () => {
    const data = chartData({
      source: dataSource({
        aggregation_group_bys: undefined,
      }),
      data: {
        results: [
          {
            'Amount sum': 20,
          },
        ],
      },
    })

    expect(data.labels).toEqual([''])
    expect(data.datasets[0].type).toBe('bar')
    expect(data.datasets[0].data).toEqual([20])
  })

  test('renders chart data with merged options', async () => {
    const wrapper = await mountComponent({
      data: {
        labels: ['A'],
        datasets: [{ type: 'line', label: 'Series', data: [10] }],
      },
      options: {
        plugins: {
          legend: {
            labels: {
              color: '#ff0000',
            },
          },
        },
      },
    })

    const chart = wrapper.findComponent({ name: 'Bar' })
    expect(chart.props('data').labels).toEqual(['A'])
    expect(chart.props('options').plugins.legend.labels.color).toBe('#ff0000')
    expect(chart.props('options').plugins.legend.position).toBe('bottom')
  })

  test('builds no-grouping pie chart data as series slices', async () => {
    const data = chartData({
      source: dataSource({
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
      }),
      data: {
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

    expect(data.labels).toEqual([
      'Amount (viewAggregationType.sum)',
      'Revenue (viewAggregationType.sum)',
    ])
    expect(data.datasets).toHaveLength(1)
    expect(data.datasets[0].type).toBe('pie')
    expect(data.datasets[0].data).toEqual([20, 10])
    expect(data.datasets[0].backgroundColor).toBeInstanceOf(Array)
  })

  test('builds grouped chart data from human result property names', async () => {
    const data = chartData({
      source: dataSource({
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
      }),
      data: {
        results: [
          {
            'Amount sum': 20,
            Category: 'Hardware',
          },
        ],
      },
    })

    expect(data.labels).toEqual(['Hardware'])
    expect(data.datasets[0].data).toEqual([20])
  })

  test('builds grouped single select labels from human result property names', async () => {
    const data = chartData({
      source: dataSource({
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
      }),
      data: {
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

    expect(data.labels).toEqual(['Hardware', 'Software'])
    expect(data.datasets[0].data).toEqual([20, 10])
  })

  test('builds chart data from technical result property names as a fallback', async () => {
    const data = chartData()

    expect(data.datasets[0].data).toEqual([20])
  })

  test('builds grouped labels from technical group-by property names as a fallback', async () => {
    const data = chartData({
      source: dataSource({
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
      }),
      data: {
        results: [
          {
            'Amount sum': 20,
            field_11: 'Hardware',
            Name: 'OTHER_VALUES',
          },
        ],
      },
    })

    expect(data.labels).toEqual(['Hardware'])
    expect(data.datasets[0].data).toEqual([20])
  })
})
