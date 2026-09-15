import { mountSuspended } from '@nuxt/test-utils/runtime'

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

  test.each(['boolean', 'rating', 'url', 'file', 'single_select', 'formula'])(
    'numeric aggregates of %s fields use the result type and direct formula',
    (originalType) => {
      const serviceType = useNuxtApp().$registry.get(
        'service',
        'local_baserow_grouped_aggregate_rows'
      )
      const fields = serviceType.getDefaultCollectionFields({
        schema: {
          items: {
            properties: {
              field_1_count: {
                type: 'number',
                original_type: originalType,
                title: 'Count',
                metadata: { aggregation: { type: 'count' } },
              },
            },
          },
        },
      })
      expect(fields).toEqual([
        {
          id: expect.any(String),
          name: 'Count',
          type: 'text',
          value: { formula: "get('current_record.field_1_count')" },
        },
      ])
    }
  )

  test('selecting a grouped source in a Table generates result columns', async () => {
    const app = useNuxtApp()
    const service = {
      id: 7,
      name: 'Grouped rows',
      type: 'local_baserow_grouped_aggregate_rows',
      table_id: 1,
      aggregation_series: [{ field_id: 2, aggregation_type: 'count' }],
      schema: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            id: { type: 'string', title: 'Id' },
            field_1: {
              type: 'object',
              original_type: 'single_select',
              title: 'Status',
            },
            field_2: {
              type: 'boolean',
              original_type: 'boolean',
              title: 'Done',
            },
            field_2_count: {
              type: 'number',
              title: 'Done count',
              metadata: {
                source_field: { display_name: 'Done' },
                aggregation: { type: 'count' },
              },
            },
          },
        },
      },
    }
    const page = { id: 1, elements: [], dataSources: [service] }
    const sharedPage = { id: 2, shared: true, elements: [], dataSources: [] }
    const builder = { id: 1, theme: {}, pages: [page, sharedPage] }
    const element = {
      id: 1,
      type: 'table',
      page_id: page.id,
      data_source_id: null,
      fields: [],
      styles: {},
      orientation: {},
    }
    await app.$store.dispatch('element/forceCreate', { page, element })
    await app.$store.dispatch('element/select', { builder, element })
    const { default: TableElementForm } =
      await import('@baserow/modules/builder/components/elements/components/forms/general/TableElementForm.vue')
    const wrapper = await mountSuspended(TableElementForm, {
      props: { defaultValues: element },
      global: {
        provide: {
          builder,
          workspace: {},
          currentPage: page,
          elementPage: page,
          mode: 'editing',
          applicationContext: { builder, page, element, mode: 'editing' },
        },
        stubs: {
          CustomStyleButton: true,
          InjectedFormulaInput: true,
          DeviceSelector: true,
          PropertyOptionForm: true,
          ServiceSchemaPropertySelector: true,
          DataSourceDropdown: {
            props: ['modelValue', 'localDataSources'],
            emits: ['update:modelValue'],
            template: `<select @change="$emit('update:modelValue', Number($event.target.value))">
              <option value="">Choose a source</option>
              <option v-for="source in localDataSources" :value="source.id">{{ source.name }}</option>
            </select>`,
          },
          SidebarExpandable: true,
        },
      },
    })
    try {
      await wrapper.get('select').setValue('7')
      const values = wrapper.emitted('values-changed').at(-1)[0]
      expect(values.data_source_id).toBe(7)
      expect(values.fields).toMatchSnapshot()
      expect(
        wrapper.findAllComponents({ name: 'SidebarExpandable' })
      ).toHaveLength(3)
    } finally {
      wrapper.unmount()
    }
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
