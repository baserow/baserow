import CorePeriodicServiceForm from '@baserow/modules/integrations/core/components/services/CorePeriodicServiceForm.vue'
import {
  ServiceType,
  TriggerServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'

export class PeriodicTriggerServiceType extends TriggerServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'periodic'
  }

  get name() {
    return this.app.i18n.t('serviceType.corePeriodic')
  }

  get description() {
    return this.app.i18n.t('serviceType.corePeriodicDescription')
  }

  get formComponent() {
    return CorePeriodicServiceForm
  }

  getDataSchema(service) {
    return service.schema
  }

  getErrorMessage({ service }) {
    if (!service.interval) {
      return this.app.i18n.t('serviceType.corePeriodicErrorIntervalMissing')
    }
    return super.getErrorMessage({ service })
  }
}
