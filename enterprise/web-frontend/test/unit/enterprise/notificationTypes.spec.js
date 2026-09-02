import { ApplicationUserLimitNotificationType } from '@baserow_enterprise/notificationTypes'
import ApplicationUserLimitNotification from '@baserow_enterprise/components/notifications/ApplicationUserLimitNotification'
import NotificationImgIcon from '@baserow/modules/core/components/notifications/NotificationImgIcon'

describe('ApplicationUserLimitNotificationType', () => {
  test('matches the backend notification type name', () => {
    expect(ApplicationUserLimitNotificationType.getType()).toBe(
      'application_user_limit'
    )
  })

  test('renders the Baserow logo icon and the dedicated content component', () => {
    const type = new ApplicationUserLimitNotificationType({ app: {} })

    expect(type.getIconComponent()).toBe(NotificationImgIcon)
    expect(type.getIconComponentProps().icon).toBeTruthy()
    expect(type.getContentComponent()).toBe(ApplicationUserLimitNotification)
  })
})
