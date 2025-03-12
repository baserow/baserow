import { NotificationType } from '@baserow/modules/core/notificationTypes'
import NotificationSenderInitialsIcon from '@baserow/modules/core/components/notifications/NotificationSenderInitialsIcon'
import CollaboratorAddedToRowNotification from '@baserow/modules/database/components/notifications/CollaboratorAddedToRowNotification'
import UserMentionInRichTextFieldNotification from '@baserow/modules/database/components/notifications/UserMentionInRichTextFieldNotification'
import FormSubmittedNotification from '@baserow/modules/database/components/notifications/FormSubmittedNotification'
import WebhookDeactivatedNotification from '@baserow/modules/database/components/notifications/WebhookDeactivatedNotification'
import WebhookPayloadTooLargeNotification from '@baserow/modules/database/components/notifications/WebhookPayloadTooLargeNotification'

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
    return {
      name: 'database-table-row',
      params: {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
        rowId: notificationData.row_id,
      },
    }
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
    return {
      name: 'database-table-row',
      params: {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
        rowId: notificationData.row_id,
      },
    }
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
    return {
      name: 'database-table-row',
      params: {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
        rowId: notificationData.row_id,
      },
    }
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
    return {
      name: 'database-table-open-webhooks',
      params: {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
      },
    }
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
    return {
      name: 'database-table-open-webhooks',
      params: {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
      },
    }
  }
}
