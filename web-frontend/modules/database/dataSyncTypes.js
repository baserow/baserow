import { Registerable } from '@baserow/modules/core/registry'

import ICalCalendarDataSync from '@baserow/modules/database/components/dataSync/ICalCalendarDataSync'
import PostgreSQLDataSync from '@baserow/modules/database/components/dataSync/PostgreSQLDataSync'

export class DataSyncType extends Registerable {
  /**
   * Should return a icon class name related to the icon that must be displayed
   * to the user.
   */
  getIconClass() {
    throw new Error('The icon class of a data sync type must be set.')
  }

  /**
   * Should return a human-readable name that indicating what the data sync does.
   */
  getName() {
    throw new Error('The name of a data type type must be set.')
  }

  /**
   * Should return the component that is added to the CreateTableModal when the
   * data sync is chosen.
   */
  getFormComponent() {
    return null
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.iconClass = this.getIconClass()

    if (this.type === null) {
      throw new Error('The type name of a data sync type must be set.')
    }
  }

  serialize() {
    return {
      type: this.type,
      iconClass: this.iconClass,
      name: this.getName(),
    }
  }

  /**
   * Indicates whether the data sync is deactivated.
   */
  isDeactivated(workspaceId) {
    return false
  }

  /**
   * When the disabled data sync is clicked, this modal will be shown.
   */
  getDeactivatedClickModal() {
    return null
  }

  /**
   * Type of the two-way sync strategy. This is just used for showing the correct
   * label. If set, then it enabled the two-way data sync.
   */
  getTwoWayDataSyncStrategy() {
    return null
  }
}

export class ICalCalendarDataSyncType extends DataSyncType {
  static getType() {
    return 'ical_calendar'
  }

  getIconClass() {
    return 'iconoir-calendar'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('dataSyncType.icalCalendar')
  }

  getFormComponent() {
    return ICalCalendarDataSync
  }
}

export class PostgreSQLDataSyncType extends DataSyncType {
  static getType() {
    return 'postgresql'
  }

  getIconClass() {
    return 'baserow-icon-postgresql'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('dataSyncType.postgresql')
  }

  getFormComponent() {
    return PostgreSQLDataSync
  }
}
