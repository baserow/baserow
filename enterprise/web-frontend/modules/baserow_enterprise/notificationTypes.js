import { NotificationType } from '@baserow/modules/core/notificationTypes'

import PeriodicDataSyncDeactivatedNotification from '@baserow_enterprise/components/notifications/PeriodicDataSyncDeactivatedNotification'
import { PeriodicIntervalFieldsConfigureDataSyncType } from '@baserow_enterprise/configureDataSyncTypes'

export class PeriodicDataSyncDeactivatedNotificationType extends NotificationType {
  static getType() {
    return 'periodic_data_sync_deactivated'
  }

  getIconComponent() {
    return null
  }

  getContentComponent() {
    return PeriodicDataSyncDeactivatedNotification
  }

  getRoute(notificationData) {
    return {
      name: 'database-table-open-configure-data-sync',
      params: {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
        selectedPage: PeriodicIntervalFieldsConfigureDataSyncType.getType(),
      },
    }
  }
}
