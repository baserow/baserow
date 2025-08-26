import { NotificationType } from '@baserow/modules/core/notificationTypes'

import PeriodicDataSyncDeactivatedNotification from '@baserow_enterprise/components/notifications/PeriodicDataSyncDeactivatedNotification'
import TwoWaySyncUpdateFailedNotification from '@baserow_enterprise/components/notifications/TwoWaySyncUpdateFailedNotification'
import TwoWaySyncDeactivatedNotification from '@baserow_enterprise/components/notifications/TwoWaySyncDeactivatedNotification'
import { PeriodicIntervalFieldsConfigureDataSyncType } from '@baserow_enterprise/configureDataSyncTypes'
import { SyncedFieldsConfigureDataSyncType } from '@baserow/modules/database/configureDataSyncTypes'

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

export class TwoWayDataSyncUpdateFiledNotificationType extends NotificationType {
  static getType() {
    return 'two_way_sync_update_failed'
  }

  getIconComponent() {
    return null
  }

  getContentComponent() {
    return TwoWaySyncUpdateFailedNotification
  }

  getRoute(notificationData) {
    return {
      name: 'database-table-open-configure-data-sync',
      params: {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
        selectedPage: SyncedFieldsConfigureDataSyncType.getType(),
      },
    }
  }
}

export class TwoWaySyncDeactivatedNotificationType extends NotificationType {
  static getType() {
    return 'two_way_sync_deactivated'
  }

  getIconComponent() {
    return null
  }

  getContentComponent() {
    return TwoWaySyncDeactivatedNotification
  }

  getRoute(notificationData) {
    return {
      name: 'database-table-open-configure-data-sync',
      params: {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
        selectedPage: SyncedFieldsConfigureDataSyncType.getType(),
      },
    }
  }
}
