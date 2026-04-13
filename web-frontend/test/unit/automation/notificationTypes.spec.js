import { WorkflowDisabledNotificationType } from '@baserow/modules/automation/notificationTypes'

describe('WorkflowDisabledNotificationType', () => {
  test('resolves the workflow route from notification data', () => {
    const type = new WorkflowDisabledNotificationType({ app: {} })

    expect(
      type.getRoute({
        automation_id: 12,
        workflow_id: 34,
      })
    ).toStrictEqual({
      name: 'automation-workflow',
      params: {
        automationId: 12,
        workflowId: 34,
      },
    })
  })
})
