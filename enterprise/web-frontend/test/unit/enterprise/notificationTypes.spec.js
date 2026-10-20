import { ApplicationUserLimitNotificationType } from '@baserow_enterprise/notificationTypes'
import ApplicationUserLimitNotification from '@baserow_enterprise/components/notifications/ApplicationUserLimitNotification'
import NotificationImgIcon from '@baserow/modules/core/components/notifications/NotificationImgIcon'
import { unwrapLazyComponent } from '@baserow/modules/core/utils/lazyComponent'

describe('ApplicationUserLimitNotificationType', () => {
  test('matches the backend notification type name', () => {
    expect(ApplicationUserLimitNotificationType.getType()).toBe(
      'application_user_limit'
    )
  })

  test('renders the Baserow logo icon and the dedicated content component', () => {
    const type = new ApplicationUserLimitNotificationType({ app: {} })

    expect(unwrapLazyComponent(type.getIconComponent())).toBe(
      NotificationImgIcon
    )
    expect(type.getIconComponentProps().icon).toBeTruthy()
    expect(unwrapLazyComponent(type.getContentComponent())).toBe(
      ApplicationUserLimitNotification
    )
  })
})
