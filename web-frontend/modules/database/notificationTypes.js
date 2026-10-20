import { NotificationType } from '@baserow/modules/core/notificationTypes'
import { tableRouteResetViewIfNeeded } from '@baserow/modules/database/utils/routing'
import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const NotificationSenderInitialsIcon = lazyComponent(
  () =>
    import('@baserow/modules/core/components/notifications/NotificationSenderInitialsIcon')
)
const CollaboratorAddedToRowNotification = lazyComponent(
  () =>
    import('@baserow/modules/database/components/notifications/CollaboratorAddedToRowNotification')
)
const UserMentionInRichTextFieldNotification = lazyComponent(
  () =>
    import('@baserow/modules/database/components/notifications/UserMentionInRichTextFieldNotification')
)
const FormSubmittedNotification = lazyComponent(
  () =>
    import('@baserow/modules/database/components/notifications/FormSubmittedNotification')
)
const WebhookDeactivatedNotification = lazyComponent(
  () =>
    import('@baserow/modules/database/components/notifications/WebhookDeactivatedNotification')
)
const WebhookPayloadTooLargeNotification = lazyComponent(
  () =>
    import('@baserow/modules/database/components/notifications/WebhookPayloadTooLargeNotification')
)

export class CollaboratorAddedToRowNotificationType extends NotificationType {
  static getType() {
    return 'collaborator_added_to_row'
  }

  getIconComponent() {
    return NotificationSenderInitialsIcon
  }

  getContentComponent() {
    return CollaboratorAddedToRowNotification
  }

  getRoute(notificationData) {
    return tableRouteResetViewIfNeeded(this.app.$router, {
      databaseId: notificationData.database_id,
      tableId: notificationData.table_id,
      rowId: notificationData.row_id,
    })
  }
}

export class FormSubmittedNotificationType extends NotificationType {
  static getType() {
    return 'form_submitted'
  }

  getIconComponent() {
    return null
  }

  getContentComponent() {
    return FormSubmittedNotification
  }

  getRoute(notificationData) {
    return tableRouteResetViewIfNeeded(this.app.$router, {
      databaseId: notificationData.database_id,
      tableId: notificationData.table_id,
      rowId: notificationData.row_id,
    })
  }
}

export class UserMentionInRichTextFieldNotificationType extends NotificationType {
  static getType() {
    return 'user_mention_in_rich_text_field'
  }

  getIconComponent() {
    return NotificationSenderInitialsIcon
  }

  getContentComponent() {
    return UserMentionInRichTextFieldNotification
  }

  getRoute(notificationData) {
    return tableRouteResetViewIfNeeded(this.app.$router, {
      databaseId: notificationData.database_id,
      tableId: notificationData.table_id,
      rowId: notificationData.row_id,
    })
  }
}

export class WebhookDeactivatedNotificationType extends NotificationType {
  static getType() {
    return 'webhook_deactivated'
  }

  getIconComponent() {
    return null
  }

  getContentComponent() {
    return WebhookDeactivatedNotification
  }

  getRoute(notificationData) {
    return tableRouteResetViewIfNeeded(
      this.app.$router,
      {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
      },
      'database-table-open-webhooks'
    )
  }
}

export class WebhookPayloadTooLargedNotificationType extends NotificationType {
  static getType() {
    return 'webhook_payload_too_large'
  }

  getIconComponent() {
    return null
  }

  getContentComponent() {
    return WebhookPayloadTooLargeNotification
  }

  getRoute(notificationData) {
    return tableRouteResetViewIfNeeded(
      this.app.$router,
      {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
      },
      'database-table-open-webhooks'
    )
  }
}
