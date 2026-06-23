import {
  CoreStartWorkflowNodeType,
  LocalBaserowFieldsUpdatedTriggerNodeType,
} from '@baserow/modules/automation/nodeTypes'

describe('LocalBaserowFieldsUpdatedTriggerNodeType label', () => {
  const makeNodeType = () =>
    new LocalBaserowFieldsUpdatedTriggerNodeType({
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

  const schema = {
    items: {
      properties: {
        field_866: { metadata: { id: 866, name: 'Name' } },
        field_868: { metadata: { id: 868, name: 'Notes' } },
      },
    },
  }

  const serviceWith = (fieldIds) => ({
    integration_id: 1,
    table_id: 5,
    field_ids: fieldIds,
    schema,
  })

  test('getFieldNames resolves all watched field names from the schema', () => {
    expect(
      makeNodeType().getFieldNames({ service: serviceWith([866, 868]) })
    ).toEqual(['Name', 'Notes'])
  })

  test('getFieldNames is empty when no field is selected', () => {
    expect(
      makeNodeType().getFieldNames({ service: { field_ids: [], schema: {} } })
    ).toEqual([])
  })

  test('label names the single selected field', () => {
    const label = makeNodeType().getDefaultLabel({
      automation: {},
      node: { service: serviceWith([866]) },
    })
    expect(label).toContain('nodeType.localBaserowFieldsUpdatedLabel')
    expect(label).toContain('Name')
    expect(label).toContain('Customers')
  })

  test('label uses a count when multiple fields are selected', () => {
    const label = makeNodeType().getDefaultLabel({
      automation: {},
      node: { service: serviceWith([866, 868]) },
    })
    expect(label).toContain('nodeType.localBaserowFieldsUpdatedMultipleLabel')
    expect(label).toContain('"count":2')
    expect(label).toContain('Customers')
  })

  test('label uses the no-field template when no field is selected', () => {
    const label = makeNodeType().getDefaultLabel({
      automation: {},
      node: { service: serviceWith([]) },
    })
    expect(label).toBe('nodeType.localBaserowFieldsUpdatedNoFieldLabel')
  })
})

describe('CoreStartWorkflowNodeType label', () => {
  const workspace = { id: 1 }
  const automations = [
    {
      id: 1,
      type: 'automation',
      workspace,
      workflows: [{ id: 101, name: 'Current workflow' }],
    },
    {
      id: 2,
      type: 'automation',
      workspace,
      workflows: [{ id: 201, name: 'Follow-up workflow' }],
    },
  ]

  const makeNodeType = () =>
    new CoreStartWorkflowNodeType({
      app: {
        $i18n: {
          t: (key, data) => (data ? `${key} ${JSON.stringify(data)}` : key),
        },
        $store: {
          getters: {
            'workspace/getSelected': workspace,
            'application/getAllOfWorkspace': () => automations,
            'automationWorkflow/getWorkflows': (automation) =>
              automation.workflows,
          },
        },
        $registry: {
          get: () => ({
            name: 'Start workflow',
          }),
        },
      },
    })

  test('label names the selected workflow from another automation', () => {
    const label = makeNodeType().getDefaultLabel({
      automation: automations[0],
      node: { service: { workflow_id: 201 } },
    })

    expect(label).toContain('nodeType.startWorkflowLabel')
    expect(label).toContain('Follow-up workflow')
  })
})
