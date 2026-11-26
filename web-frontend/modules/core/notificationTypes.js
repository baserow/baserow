import { Registerable } from '@baserow/modules/core/registry'
import NotificationSenderInitialsIcon from '@baserow/modules/core/components/notifications/NotificationSenderInitialsIcon'
import WorkspaceInvitationCreatedNotification from '@baserow/modules/core/components/notifications/WorkspaceInvitationCreatedNotification'
import WorkspaceInvitationAcceptedNotification from '@baserow/modules/core/components/notifications/WorkspaceInvitationAcceptedNotification'
import WorkspaceInvitationRejectedNotification from '@baserow/modules/core/components/notifications/WorkspaceInvitationRejectedNotification'
import BaserowVersionUpgradeNotification from '@baserow/modules/core/components/notifications/BaserowVersionUpgradeNotification'
import AbuseReportCreatedNotification from '@baserow/modules/core/components/notifications/AbuseReportCreatedNotification'
import UserTemplateNotification from '@baserow/modules/core/components/notifications/UserTemplateNotification'
import NotificationImgIcon from '@baserow/modules/core/components/notifications/NotificationImgIcon'
import BaserowIcon from '@baserow/modules/core/static/img/logoOnly.svg?url'

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

export class UserTemplateNotificationType extends NotificationType {
  getIconComponent() {
    return NotificationImgIcon
  }

  getIconComponentProps() {
    return { icon: BaserowIcon }
  }

  getContentComponent() {
    return UserTemplateNotification
  }

  getTitleKey() {
    throw new Error('getTitleKey not implemented')
  }
}

export class UserTemplateAdminNotificationType extends UserTemplateNotificationType {
  getAdminTab() {
    throw new Error('getAdminTab not implemented')
  }

  getRoute(notificationData) {
    return {
      name: 'admin-templates',
      query: {
        tab: this.getAdminTab(),
        template: notificationData.template_id,
      },
    }
  }
}

export class UserTemplateInReviewNotificationType extends UserTemplateAdminNotificationType {
  static getType() {
    return 'user_template_in_review'
  }

  getTitleKey() {
    return 'userTemplateNotification.inReview'
  }

  getAdminTab() {
    return 'in_review'
  }
}

export class BlockedUserTemplateChangedNotificationType extends UserTemplateAdminNotificationType {
  static getType() {
    return 'blocked_user_template_changed'
  }

  getTitleKey() {
    return 'userTemplateNotification.blockedChanged'
  }

  getAdminTab() {
    return 'blocked'
  }
}

export class UserTemplateAuthorNotificationType extends UserTemplateNotificationType {
  getRoute(notificationData) {
    return {
      name: 'template',
      params: { slug: notificationData.template_slug },
    }
  }
}

export class UserTemplateApprovedNotificationType extends UserTemplateAuthorNotificationType {
  static getType() {
    return 'user_template_approved'
  }

  getTitleKey() {
    return 'userTemplateNotification.approved'
  }
}

export class UserTemplateRejectedNotificationType extends UserTemplateAuthorNotificationType {
  static getType() {
    return 'user_template_rejected'
  }

  getTitleKey() {
    return 'userTemplateNotification.rejected'
  }
}

export class UserTemplateChangeRejectedNotificationType extends UserTemplateAuthorNotificationType {
  static getType() {
    return 'user_template_change_rejected'
  }

  getTitleKey() {
    return 'userTemplateNotification.changeRejected'
  }
}

export class UserTemplateUnlistedNotificationType extends UserTemplateAuthorNotificationType {
  static getType() {
    return 'user_template_unlisted'
  }

  getTitleKey() {
    return 'userTemplateNotification.unlisted'
  }
}

export class UserTemplateBlockedNotificationType extends UserTemplateAuthorNotificationType {
  static getType() {
    return 'user_template_blocked'
  }

  getTitleKey() {
    return 'userTemplateNotification.blocked'
  }
}

export class UserTemplateUnblockedNotificationType extends UserTemplateAuthorNotificationType {
  static getType() {
    return 'user_template_unblocked'
  }

  getTitleKey() {
    return 'userTemplateNotification.unblocked'
  }
}
