import { Registerable } from '@baserow/modules/core/registry'
import BaserowIcon from '@baserow/modules/core/static/img/logoOnly.svg?url'
import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const NotificationSenderInitialsIcon = lazyComponent(
  () =>
    import('@baserow/modules/core/components/notifications/NotificationSenderInitialsIcon')
)
const WorkspaceInvitationCreatedNotification = lazyComponent(
  () =>
    import('@baserow/modules/core/components/notifications/WorkspaceInvitationCreatedNotification')
)
const WorkspaceInvitationAcceptedNotification = lazyComponent(
  () =>
    import('@baserow/modules/core/components/notifications/WorkspaceInvitationAcceptedNotification')
)
const WorkspaceInvitationRejectedNotification = lazyComponent(
  () =>
    import('@baserow/modules/core/components/notifications/WorkspaceInvitationRejectedNotification')
)
const BaserowVersionUpgradeNotification = lazyComponent(
  () =>
    import('@baserow/modules/core/components/notifications/BaserowVersionUpgradeNotification')
)
const AbuseReportCreatedNotification = lazyComponent(
  () =>
    import('@baserow/modules/core/components/notifications/AbuseReportCreatedNotification')
)
const NotificationImgIcon = lazyComponent(
  () =>
    import('@baserow/modules/core/components/notifications/NotificationImgIcon')
)

export class NotificationType extends Registerable {
  getIconComponent() {
    throw new Error('getIconComponent not implemented')
  }

  getContentComponent() {
    throw new Error('getContentComponent not implemented')
  }

  getIconComponentProps() {
    return {}
  }

  /**
   * Should return the nuxt route of the page where to redirect to if the user clicks
   * on the notification. Note that the backend also uses this to create a link in
   * external communication like the email, and if anything changes in this method,
   * the `safe_route_data_parameters` then might need to be updated as well. If
   * `null` is returned, it means that the notification is not clickable.
   */
  getRoute(notificationData) {
    return null
  }
}

export class WorkspaceInvitationCreatedNotificationType extends NotificationType {
  static getType() {
    return 'workspace_invitation_created'
  }

  getIconComponent() {
    return NotificationSenderInitialsIcon
  }

  getContentComponent() {
    return WorkspaceInvitationCreatedNotification
  }

  getRoute(notificationData) {
    return { name: 'all-workspaces' }
  }
}

export class WorkspaceInvitationAcceptedNotificationType extends NotificationType {
  static getType() {
    return 'workspace_invitation_accepted'
  }

  getIconComponent() {
    return NotificationSenderInitialsIcon
  }

  getContentComponent() {
    return WorkspaceInvitationAcceptedNotification
  }
}

export class WorkspaceInvitationRejectedNotificationType extends NotificationType {
  static getType() {
    return 'workspace_invitation_rejected'
  }

  getIconComponent() {
    return NotificationSenderInitialsIcon
  }

  getContentComponent() {
    return WorkspaceInvitationRejectedNotification
  }
}

export class BaserowVersionUpgradeNotificationType extends NotificationType {
  static getType() {
    return 'baserow_version_upgrade'
  }

  getIconComponent() {
    return NotificationImgIcon
  }

  getIconComponentProps() {
    return { icon: BaserowIcon }
  }

  getContentComponent() {
    return BaserowVersionUpgradeNotification
  }
}

export class AbuseReportCreatedNotificationType extends NotificationType {
  static getType() {
    return 'abuse_report_created'
  }

  getIconComponent() {
    return NotificationImgIcon
  }

  getIconComponentProps() {
    return { icon: BaserowIcon }
  }

  getContentComponent() {
    return AbuseReportCreatedNotification
  }
}
