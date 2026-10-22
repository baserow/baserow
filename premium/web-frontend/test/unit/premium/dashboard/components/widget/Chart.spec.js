import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import Chart from '@baserow_premium/components/Chart'
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

  test('truncates axis labels without changing full tooltip labels', async () => {
    const label = 'Alice and Bob and Charlie with a very long name'
    const data = {
      labels: [label],
      datasets: [{ type: 'bar', data: [12] }],
    }
    const wrapper = await mountComponent({ data })
    const chart = wrapper.findComponent({ name: 'Bar' })
    const callback = chart.props('options').scales.x.ticks.callback
    const scale = {
      getLabelForValue: () => label,
      chart: { data: { labels: [label] }, chartArea: { width: 350 } },
    }
    expect(callback.call(scale, 0)).toBe(`${label.slice(0, 24)}…`)
    expect(
      callback.call({ ...scale, getLabelForValue: () => 'Alice' }, 0)
    ).toBe('Alice')
    scale.chart.chartArea.width = 70
    expect(callback.call(scale, 0)).toBe(`${label.slice(0, 9)}…`)
    scale.chart.data.labels = [label, label]
    expect(callback.call(scale, 0)).toBe(`${label.slice(0, 4)}…`)
    scale.chart.chartArea = undefined
    scale.chart.width = 140
    expect(callback.call(scale, 0)).toBe(`${label.slice(0, 9)}…`)
    expect(chart.props('data').labels).toEqual([label])
  })

  test.each([
    ['text', '', 'chart.empty'],
    ['text', '   ', '   '],
    ['number', 0, 0],
    ['rating', 0, 0],
    ['boolean', true, 'chart.true'],
    ['boolean', false, 'chart.false'],
    ['date', null, 'chart.empty'],
    ['duration', null, 'chart.empty'],
  ])('uses field emptiness for %s value %s', (type, value, expected) => {
    const source = dataSource({
      aggregation_group_bys: [{ field_id: 11 }],
      context_data: { fields: { field_11: { type } } },
    })
    const fieldType = testApp.$registry.get('field', type)
    const isEmpty = vi.spyOn(fieldType, 'isEmptyForGrouping')
    try {
      const data = chartData({
        source,
        data: { results: [{ field_11: value, 'Amount sum': 12 }] },
      })
      expect(data.labels).toEqual([expected])
      if (value !== null) {
        expect(isEmpty).toHaveBeenCalledWith(
          source.context_data.fields.field_11,
          value
        )
      }
    } finally {
      isEmpty.mockRestore()
    }
  })

  test.each(['BAR', 'LINE', 'PIE', 'DOUGHNUT'])(
    'uses saved series colors for %s charts',
    (type) => {
      const source = dataSource({
        aggregation_group_bys: [{ field_id: 11 }],
        context_data: { fields: { field_11: { type: 'text' } } },
      })
      const seriesConfig = [
        { series_id: 1, series_chart_type: type, series_color: '#aabbcc' },
      ]
      const data = chartData({
        source,
        seriesConfig,
        data: { results: [{ field_11: 'Alpha', 'Amount sum': 5 }] },
      })
      if (['PIE', 'DOUGHNUT'].includes(type)) {
        expect(data.datasets[0].backgroundColor).toEqual(['#aabbcc'])
      } else {
        expect(data.datasets[0].backgroundColor).toBe('#aabbcc')
        expect(data.datasets[0].borderColor).toBe('#aabbcc')
      }
      source.aggregation_group_bys = []
      const ungrouped = chartData({
        source,
        seriesConfig,
        data: { results: [{ 'Amount sum': 5 }] },
      })
      expect(ungrouped.datasets[0].backgroundColor).toEqual(
        ['PIE', 'DOUGHNUT'].includes(type) ? ['#aabbcc'] : '#aabbcc'
      )
    }
  )

  test.each(['PIE', 'DOUGHNUT'])(
    'generates a shade per slice from a custom %s series color',
    (type) => {
      const source = dataSource({
        aggregation_group_bys: [{ field_id: 11 }],
        context_data: { fields: { field_11: { type: 'text' } } },
      })
      const colors = chartData({
        source,
        seriesConfig: [
          { series_id: 1, series_chart_type: type, series_color: '#808080' },
        ],
        data: {
          results: Array.from({ length: 12 }, (_, index) => ({
            field_11: `Group ${index}`,
            'Amount sum': index + 1,
          })),
        },
      }).datasets[0].backgroundColor
      expect(colors).toHaveLength(12)
      expect(colors[0]).toBe('#808080')
      expect(new Set(colors).size).toBe(12)
      expect(colors.every((color) => /^#[0-9a-f]{6,8}$/i.test(color))).toBe(
        true
      )
      expect(parseInt(colors[1].slice(1, 3), 16)).toBeLessThan(128)
      expect(parseInt(colors[2].slice(1, 3), 16)).toBeGreaterThan(128)
    }
  )

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

  test.each(['BAR', 'PIE'])(
    'renders empty multiple selections in %s charts',
    async (chartType) => {
      const options = [
        { id: 1, value: 'Alpha', color: 'red' },
        { id: 2, value: 'Beta', color: 'blue' },
      ]
      const source = dataSource({
        aggregation_group_bys: [{ field_id: 11 }],
        context_data: {
          fields: {
            field_11: { type: 'multiple_select', select_options: options },
          },
        },
      })
      const data = chartData({
        source,
        seriesConfig: [{ series_id: 1, series_chart_type: chartType }],
        data: {
          results: [
            { field_11: [], 'Amount sum': 12 },
            { field_11: null, 'Amount sum': 8 },
            { field_11: [options[0]], 'Amount sum': 3 },
            { field_11: options, 'Amount sum': 5 },
            { field_11: [1, 2], 'Amount sum': 6 },
            { field_11: 'OTHER_VALUES', 'Amount sum': 7 },
          ],
        },
      })
      const wrapper = await mountComponent({ data })
      const chartProps = wrapper
        .findComponent({ name: chartType === 'BAR' ? 'Bar' : 'Pie' })
        .props('data')
      expect(chartProps.labels).toEqual([
        'chart.empty',
        'chart.empty',
        'Alpha',
        'Alpha, Beta',
        'Alpha, Beta',
        'chart.other',
      ])
      expect(chartProps.datasets[0].data).toEqual([12, 8, 3, 5, 6, 7])
    }
  )
})

describe('Grouped relation chart labels', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test.each(['link_row', 'multiple_collaborators'])(
    'uses the backend display value for %s group labels',
    (type) => {
      const source = {
        type: 'local_baserow_grouped_aggregate_rows',
        aggregation_series: [{ id: 1, field_id: 10, aggregation_type: 'sum' }],
        aggregation_group_bys: [{ field_id: 11 }],
        schema: {
          items: {
            properties: {
              field_10_sum: {
                title: 'Amount sum',
                metadata: {
                  display_name: 'Amount sum',
                  source_field: { display_name: 'Amount' },
                  aggregation: { type: 'sum' },
                },
              },
            },
          },
        },
        context_data: { fields: { field_11: { type } } },
      }

      const data = getDashboardChartData({
        dataSource: source,
        dataSourceData: {
          results: [
            {
              id: 'Alpha',
              field_11: [{ id: 1, value: 'Alpha' }],
              'Amount sum': 12,
            },
            { id: '-', field_11: null, 'Amount sum': 5 },
            { id: '-', field_11: [], 'Amount sum': 6 },
            { id: 'OTHER_VALUES', field_11: 'OTHER_VALUES', 'Amount sum': 7 },
          ],
        },
        seriesConfig: [{ series_id: 1, series_chart_type: 'BAR' }],
        $registry: testApp.$registry,
        $t: (key) => key,
      })

      expect(data.labels).toEqual([
        'Alpha',
        'chart.empty',
        'chart.empty',
        'chart.other',
      ])
    }
  )
})
