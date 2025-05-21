import {
  ServiceType,
  ActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import CoreHTTPRequestServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPRequestServiceForm.vue'

export class CoreHTTPRequestServiceType extends ActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'http_request'
  }

  get name() {
    return this.app.i18n.t('serviceType.coreHTTPRequest')
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
