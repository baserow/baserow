import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import CoreHTTPRequestServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPRequestServiceForm.vue'

export class CoreHTTPRequestServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'http_request'
  }

  get name() {
    return this.app.i18n.t('serviceType.coreHTTPRequest')
  }

  isInError({ service }) {
    if (service === undefined) {
      return false
    }
    return !service.url
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreHTTPRequestServiceForm
  }

  getOrder() {
    return 5
  }
}
