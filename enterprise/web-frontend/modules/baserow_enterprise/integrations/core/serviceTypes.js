import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import CoreCodeServiceForm from '@baserow_enterprise/integrations/core/components/services/CoreCodeServiceForm.vue'

export class CoreCodeServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'code'
  }

  get icon() {
    return 'iconoir-code'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreCode')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreCodeDescription')
  }

  getErrorMessage({ service }) {
    if (
      service !== undefined &&
      service.code !== undefined &&
      !service.code.formula
    ) {
      return this.app.$i18n.t('serviceType.errorCodeMissing')
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreCodeServiceForm
  }

  getOrder() {
    return 4
  }
}
