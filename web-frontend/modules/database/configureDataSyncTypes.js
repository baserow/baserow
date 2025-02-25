import { Registerable } from '@baserow/modules/core/registry'
import ConfigureDataSyncVisibleFields from '@baserow/modules/database/components/dataSync/ConfigureDataSyncVisibleFields'
import ConfigureDataSyncSettings from '@baserow/modules/database/components/dataSync/ConfigureDataSyncSettings'

export class ConfigureDataSyncType extends Registerable {
  get name() {
    throw new Error(
      'name getter must be implemented in the ConfigureDataSyncType.'
    )
  }

  get iconClass() {
    throw new Error(
      'iconClass getter must be implemented in the ConfigureDataSyncType.'
    )
  }

  get component() {
    throw new Error(
      'component getter must be implemented in the ConfigureDataSyncType.'
    )
  }
}

export class SyncedFieldsConfigureDataSyncType extends ConfigureDataSyncType {
  static getType() {
    return 'synced-fields'
  }

  get name() {
    return this.app.i18n.t('configureDataSyncModal.syncedFields')
  }

  get iconClass() {
    return 'iconoir-switch-on'
  }

  get component() {
    return ConfigureDataSyncVisibleFields
  }
}

export class SettingsConfigureDataSyncType extends ConfigureDataSyncType {
  static getType() {
    return 'settings'
  }

  get name() {
    return this.app.i18n.t('configureDataSyncModal.syncSettings')
  }

  get iconClass() {
    return 'iconoir-settings'
  }

  get component() {
    return ConfigureDataSyncSettings
  }
}
