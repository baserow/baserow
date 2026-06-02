import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import CoreCodeServiceForm from '@baserow_enterprise/integrations/core/components/services/CoreCodeServiceForm.vue'

export const CORE_CODE_SERVICE_DEFAULT_CODE = `function main(context) {
  return {
    message: 'Hello from Baserow',
  }
}`

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

  getDefaultValues(service, values) {
    const defaultValues = super.getDefaultValues(service, values)
    if (!defaultValues.code) {
      return {
        ...defaultValues,
        code: CORE_CODE_SERVICE_DEFAULT_CODE,
      }
    }

    return defaultValues
  }

  getErrorMessage({ service }) {
    if (service !== undefined && service.code !== undefined && !service.code) {
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
