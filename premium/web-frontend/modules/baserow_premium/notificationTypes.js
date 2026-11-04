import { NotificationType } from '@baserow/modules/core/notificationTypes'
import { tableRouteResetViewIfNeeded } from '@baserow/modules/database/utils/routing'
import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const RowCommentMentionNotification = lazyComponent(
  () =>
    import('@baserow_premium/components/row_comments/RowCommentMentionNotification')
)
const RowCommentNotification = lazyComponent(
  () =>
    import('@baserow_premium/components/row_comments/RowCommentNotification')
)
const NotificationSenderInitialsIcon = lazyComponent(
  () =>
    import('@baserow/modules/core/components/notifications/NotificationSenderInitialsIcon')
)

export class RowCommentMentionNotificationType extends NotificationType {
  static getType() {
    return 'row_comment_mention'
  }

  getIconComponent() {
    return NotificationSenderInitialsIcon
  }

  getContentComponent() {
    return RowCommentMentionNotification
  }

  getRoute(notificationData) {
    return tableRouteResetViewIfNeeded(this.app.$router, {
      databaseId: notificationData.database_id,
      tableId: notificationData.table_id,
      rowId: notificationData.row_id,
    })
  }
}

export class RowCommentNotificationType extends NotificationType {
  static getType() {
    return 'row_comment'
  }

  getIconComponent() {
    return NotificationSenderInitialsIcon
  }

  getContentComponent() {
    return RowCommentNotification
  }

  getRoute(notificationData) {
    return tableRouteResetViewIfNeeded(this.app.$router, {
      databaseId: notificationData.database_id,
      tableId: notificationData.table_id,
      rowId: notificationData.row_id,
    })
  }
}
