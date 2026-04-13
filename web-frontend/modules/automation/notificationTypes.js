import { NotificationType } from '@baserow/modules/core/notificationTypes'
import WorkflowDisabledNotification from '@baserow/modules/automation/components/notifications/WorkflowDisabledNotification'

export class WorkflowDisabledNotificationType extends NotificationType {
  static getType() {
    return 'automation_workflow_disabled'
  }

  getIconComponent() {
    return null
  }

  getContentComponent() {
    return WorkflowDisabledNotification
  }

  getRoute(notificationData) {
    return {
      name: 'automation-workflow',
      params: {
        automationId: notificationData.automation_id,
        workflowId: notificationData.workflow_id,
      },
    }
  }
}
