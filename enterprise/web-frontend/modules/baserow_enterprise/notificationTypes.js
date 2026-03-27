import { NotificationType } from '@baserow/modules/core/notificationTypes'

import DataScanNewResultsNotification from '@baserow_enterprise/components/notifications/DataScanNewResultsNotification'
import PeriodicDataSyncDeactivatedNotification from '@baserow_enterprise/components/notifications/PeriodicDataSyncDeactivatedNotification'
import TwoWaySyncUpdateFailedNotification from '@baserow_enterprise/components/notifications/TwoWaySyncUpdateFailedNotification'
import TwoWaySyncDeactivatedNotification from '@baserow_enterprise/components/notifications/TwoWaySyncDeactivatedNotification'
import { PeriodicIntervalFieldsConfigureDataSyncType } from '@baserow_enterprise/configureDataSyncTypes'
import { SyncedFieldsConfigureDataSyncType } from '@baserow/modules/database/configureDataSyncTypes'
import { tableRouteResetViewIfNeeded } from '@baserow/modules/database/utils/routing'

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
    return tableRouteResetViewIfNeeded(
      this.app.$router,
      {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
        selectedPage: PeriodicIntervalFieldsConfigureDataSyncType.getType(),
      },
      'database-table-open-configure-data-sync'
    )
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
    return tableRouteResetViewIfNeeded(
      this.app.$router,
      {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
        selectedPage: SyncedFieldsConfigureDataSyncType.getType(),
      },
      'database-table-open-configure-data-sync'
    )
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
    return tableRouteResetViewIfNeeded(
      this.app.$router,
      {
        databaseId: notificationData.database_id,
        tableId: notificationData.table_id,
        selectedPage: SyncedFieldsConfigureDataSyncType.getType(),
      },
      'database-table-open-configure-data-sync'
    )
  }
}

export class DataScanNewResultsNotificationType extends NotificationType {
  static getType() {
    return 'data_scan_new_results'
  }

  getIconComponent() {
    return null
  }

  getContentComponent() {
    return DataScanNewResultsNotification
  }

  getRoute(notificationData) {
    return {
      name: 'admin-data-scanner-results',
      query: {
        scan_id: notificationData.scan_id,
        scan_name: notificationData.scan_name,
      },
    }
  }
}
