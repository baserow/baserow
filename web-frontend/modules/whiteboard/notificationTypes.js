import { NotificationType } from '@baserow/modules/core/notificationTypes'
import NotificationSenderInitialsIcon from '@baserow/modules/core/components/notifications/NotificationSenderInitialsIcon'
import WhiteboardCommentMentionNotification from '@baserow/modules/whiteboard/components/comments/WhiteboardCommentMentionNotification.vue'
import WhiteboardCommentReplyNotification from '@baserow/modules/whiteboard/components/comments/WhiteboardCommentReplyNotification.vue'

function whiteboardRoute(notificationData) {
  return {
    name: 'whiteboard-application',
    params: { whiteboardId: notificationData.whiteboard_id },
    query: { comment: notificationData.comment_id },
  }
}

export class WhiteboardCommentMentionNotificationType extends NotificationType {
  static getType() {
    return 'whiteboard_comment_mention'
  }

  getIconComponent() {
    return NotificationSenderInitialsIcon
  }

  getContentComponent() {
    return WhiteboardCommentMentionNotification
  }

  getRoute(notificationData) {
    return whiteboardRoute(notificationData)
  }
}

export class WhiteboardCommentReplyNotificationType extends NotificationType {
  static getType() {
    return 'whiteboard_comment_reply'
  }

  getIconComponent() {
    return NotificationSenderInitialsIcon
  }

  getContentComponent() {
    return WhiteboardCommentReplyNotification
  }

  getRoute(notificationData) {
    return whiteboardRoute(notificationData)
  }
}
