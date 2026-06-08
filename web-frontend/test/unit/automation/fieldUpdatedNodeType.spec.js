import { LocalBaserowFieldUpdatedTriggerNodeType } from '@baserow/modules/automation/nodeTypes'

describe('LocalBaserowFieldUpdatedTriggerNodeType label', () => {
  const makeNodeType = () =>
    new LocalBaserowFieldUpdatedTriggerNodeType({
      app: {
        $i18n: {
          t: (key, data) => (data ? `${key} ${JSON.stringify(data)}` : key),
        },
        $store: {
          getters: {
            'integration/getIntegrationById': () => ({
              context_data: {
                databases: [{ tables: [{ id: 5, name: 'Customers' }] }],
              },
            }),
          },
        },
      },
    })

  const serviceWithField = {
    integration_id: 1,
    table_id: 5,
    field_id: 868,
    schema: {
      items: {
        properties: {
          field_866: { metadata: { id: 866, name: 'Name' } },
          field_868: { metadata: { id: 868, name: 'Notes' } },
        },
      },
    },
  }

  test('getFieldName resolves the watched field name from the schema', () => {
    expect(makeNodeType().getFieldName({ service: serviceWithField })).toBe(
      'Notes'
    )
  })

  test('getFieldName is null when no field is selected', () => {
    expect(
      makeNodeType().getFieldName({ service: { field_id: null, schema: {} } })
    ).toBe(null)
  })

  test('label uses the field + table template when a field is selected', () => {
    const label = makeNodeType().getDefaultLabel({
      automation: {},
      node: { service: serviceWithField },
    })
    expect(label).toContain('nodeType.localBaserowFieldUpdatedLabel')
    expect(label).toContain('Notes')
    expect(label).toContain('Customers')
  })

  test('label uses the no-field template when no field is selected', () => {
    const label = makeNodeType().getDefaultLabel({
      automation: {},
      node: {
        service: { integration_id: 1, table_id: 5, field_id: null, schema: {} },
      },
    })
    expect(label).toBe('nodeType.localBaserowFieldUpdatedNoFieldLabel')
  })
})
