import { CoreStartWorkflowServiceType } from '@baserow/modules/integrations/core/serviceTypes'

describe('CoreStartWorkflowServiceType', () => {
  const workspace = { id: 1 }
  const automations = [
    {
      id: 1,
      type: 'automation',
      workspace,
      workflows: [
        { id: 101, name: 'Manual workflow', immediate_dispatch: true },
        { id: 102, name: 'Webhook workflow', immediate_dispatch: false },
      ],
    },
  ]

  const makeServiceType = () =>
    new CoreStartWorkflowServiceType({
      app: {
        $i18n: {
          t: (key) => key,
        },
        $store: {
          getters: {
            'workspace/getSelected': workspace,
            'application/getAllOfWorkspace': () => automations,
            'automationWorkflow/getWorkflows': (automation) =>
              automation.workflows,
          },
        },
      },
    })

  test('returns an error when the selected workflow cannot be immediately dispatched', () => {
    expect(
      makeServiceType().getErrorMessage({
        service: { workflow_id: 102 },
      })
    ).toBe('serviceType.errorWorkflowNotImmediateDispatch')
  })

  test('does not return an error when the selected workflow can be immediately dispatched', () => {
    expect(
      makeServiceType().getErrorMessage({
        service: { workflow_id: 101 },
      })
    ).toBe(null)
  })
})
