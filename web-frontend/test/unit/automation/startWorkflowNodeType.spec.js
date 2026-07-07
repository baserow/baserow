import { CoreStartWorkflowNodeType } from '@baserow/modules/automation/nodeTypes'

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
