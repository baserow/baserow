import { NotificationType } from '@baserow/modules/core/notificationTypes'
import Icon from '@baserow/modules/core/components/Icon'
import WorkflowDisabledNotification from '@baserow/modules/automation/components/notifications/WorkflowDisabledNotification'

export class WorkflowDisabledNotificationType extends NotificationType {
  static getType() {
    return 'automation_workflow_disabled'
  }

  getIconComponent() {
    return () => (
      <Icon
        class="notification-panel__notification-automation-icon"
        icon="baserow-icon-automation"
        type="secondary"
        size="large"
      />
    )
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
