import { defineAsyncComponent } from 'vue'
import { ConfigureDataSyncType } from '@baserow/modules/database/configureDataSyncTypes'

const ConfigureDataSyncPeriodicInterval = defineAsyncComponent({
  loader: () =>
    import('@baserow_enterprise/components/dataSync/ConfigureDataSyncPeriodicInterval'),
})

export class PeriodicIntervalFieldsConfigureDataSyncType extends ConfigureDataSyncType {
  static getType() {
    return 'periodic-interval'
  }

  get name() {
    return this.app.$i18n.t('configureDataSyncModal.periodicInterval')
  }

  get iconClass() {
    return 'iconoir-timer'
  }

  get component() {
    return ConfigureDataSyncPeriodicInterval
  }
}
