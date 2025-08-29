import PeriodicTriggerServiceForm from '@baserow/modules/automation/components/services/PeriodicTriggerServiceForm'
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
    return this.app.i18n.t('serviceType.periodicTrigger')
  }

  get description() {
    return this.app.i18n.t('serviceType.periodicTriggerDescription')
  }

  get formComponent() {
    return PeriodicTriggerServiceForm
  }

  getDataSchema(service) {
    return service.schema
  }

  isInError() {
    return false
  }
}
