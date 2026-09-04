describe('Premium integrations service types', () => {
  test('LocalBaserowGroupedAggregateRowsServiceType is registered as a builder data source', () => {
    const testApp = useNuxtApp()
    const serviceType = testApp.$registry.get(
      'service',
      'local_baserow_grouped_aggregate_rows'
    )

    expect(serviceType).toBeDefined()
    expect(serviceType.isDataSource).toBe(true)
    expect(serviceType.returnsList).toBe(true)
    expect(serviceType.supportsPagination).toBe(false)
    expect(serviceType.getIdProperty()).toBe('id')
    expect(serviceType.parseRecordId('Selected')).toBe('Selected')
    expect(serviceType.getRecordNameFromId({}, 'Selected')).toBe('Selected')
    expect(serviceType.formComponent).toBeDefined()
    expect(serviceType.integrationType.getType()).toBe('local_baserow')
  })

  test('LocalBaserowGroupedAggregateRowsServiceType exposes the backend list schema', () => {
    const testApp = useNuxtApp()
    const serviceType = testApp.$registry.get(
      'service',
      'local_baserow_grouped_aggregate_rows'
    )

    const service = {
      schema: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            field_1: { type: 'string', title: 'Category' },
            field_3: {
              type: 'object',
              title: 'Status',
              metadata: {
                type: 'single_select',
              },
            },
            field_2_sum: { type: 'number', title: 'Amount sum' },
            field_4_sum: {
              type: 'number',
              title: 'Other amount sum',
              metadata: {
                display_name: 'Other amount sum',
                source_field: {
                  display_name: 'Other amount',
                },
                aggregation: {
                  type: 'sum',
                },
              },
            },
          },
        },
      },
    }

    expect(serviceType.getDataSchema(service)).toEqual(service.schema)
    expect(serviceType.prepareValuePath(service, ['field_2_sum'])).toEqual([
      'Amount sum',
    ])
    expect(serviceType.prepareValuePath(service, ['field_1'])).toEqual([
      'Category',
    ])
    expect(
      serviceType.prepareValuePath(service, ['field_2_sum', 'value'])
    ).toEqual(['Amount sum', 'value'])
    expect(serviceType.getSchemaPropertyDisplayName(service, 'field_1')).toBe(
      'Category'
    )
    expect(
      serviceType.getSchemaPropertyDisplayName(service, 'field_4_sum')
    ).toBe('Other amount')
    expect(
      serviceType.getRecordName(
        {
          ...service,
          aggregation_group_bys: [{ field_id: 3 }],
        },
        { id: 0, field_3: { id: 1, value: 'Selected' } }
      )
    ).toBe('Selected')
    expect(
      serviceType.getRecordName(
        {
          ...service,
          aggregation_group_bys: [{ field_id: 1 }],
        },
        { id: 'Category A', field_1: 'Category A' }
      )
    ).toBe('Category A')
  })

  test('LocalBaserowGroupedAggregateRowsServiceType reports an error when no series defined', () => {
    const testApp = useNuxtApp()
    const serviceType = testApp.$registry.get(
      'service',
      'local_baserow_grouped_aggregate_rows'
    )

    const error = serviceType.getErrorMessage({
      service: {
        table_id: 1,
        aggregation_series: [],
        filters: [],
      },
    })
    expect(error).toBeTruthy()
  })

  test('LocalBaserowGroupedAggregateRowsServiceType reports an error when a series is incomplete', () => {
    const testApp = useNuxtApp()
    const serviceType = testApp.$registry.get(
      'service',
      'local_baserow_grouped_aggregate_rows'
    )

    const error = serviceType.getErrorMessage({
      service: {
        table_id: 1,
        aggregation_series: [{ field_id: null, aggregation_type: 'sum' }],
        filters: [],
      },
    })
    expect(error).toBeTruthy()
  })

  test('LocalBaserowGroupedAggregateRowsServiceType resets configuration on table change', () => {
    const testApp = useNuxtApp()
    const serviceType = testApp.$registry.get(
      'service',
      'local_baserow_grouped_aggregate_rows'
    )

    const newValues = serviceType.beforeUpdate(
      {
        table_id: 2,
        filters: [{ id: 1 }],
        aggregation_series: [{ field_id: 1, aggregation_type: 'sum' }],
        aggregation_group_bys: [{ field_id: 2 }],
        aggregation_sorts: [{ reference: 'field_1_sum', direction: 'ASC' }],
      },
      { table_id: 1 }
    )
    expect(newValues.filters).toEqual([])
    expect(newValues.aggregation_series).toEqual([])
    expect(newValues.aggregation_group_bys).toEqual([])
    expect(newValues.aggregation_sorts).toEqual([])
  })
})
