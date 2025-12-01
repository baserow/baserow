import CoreHTTPTriggerServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPTriggerServiceForm'
import {
  ServiceType,
  TriggerServiceTypeMixin,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import CoreHTTPRequestServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPRequestServiceForm'
import CoreSMTPEmailServiceForm from '@baserow/modules/integrations/core/components/services/CoreSMTPEmailServiceForm'
import CoreRouterServiceForm from '@baserow/modules/integrations/core/components/services/CoreRouterServiceForm'
import CoreIteratorServiceForm from '@baserow/modules/integrations/core/components/services/CoreIteratorServiceForm'
import CorePeriodicServiceForm from '@baserow/modules/integrations/core/components/services/CorePeriodicServiceForm.vue'

export class CoreHTTPRequestServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'http_request'
  }

  get icon() {
    return 'iconoir-cloud-upload'
  }

  get name() {
    return this.app.i18n.t('serviceType.coreHTTPRequest')
  }

  get description() {
    return this.app.i18n.t('serviceType.coreHTTPRequestDescription')
  }

  getErrorMessage({ service }) {
    // We check undefined because the url is not returned in public mode the
    // property is just ignored
    if (
      service !== undefined &&
      service.url !== undefined &&
      !service.url.formula
    ) {
      return this.app.i18n.t('serviceType.errorUrlMissing')
    }

    return super.getErrorMessage({ service })
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

export class CoreSMTPEmailServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'smtp_email'
  }

  get name() {
    return this.app.i18n.t('serviceType.coreSMTPEmail')
  }

  get description() {
    return this.app.i18n.t('serviceType.coreSMTPEmailDescription')
  }

  get icon() {
    return 'iconoir-send-mail'
  }

  getErrorMessage({ service }) {
    if (
      service !== undefined &&
      service.from_email !== undefined &&
      !service.from_email.formula
    ) {
      return this.app.i18n.t('serviceType.errorFromEmailMissing')
    }

    if (
      service !== undefined &&
      service.to_emails !== undefined &&
      !service.to_emails.formula
    ) {
      return this.app.i18n.t('serviceType.errorToEmailsMissing')
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreSMTPEmailServiceForm
  }

  getOrder() {
    return 6
  }
}

export class CoreRouterServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'router'
  }

  get name() {
    return this.app.i18n.t('serviceType.coreRouter')
  }

  get description() {
    return this.app.i18n.t('serviceType.coreRouterDescription')
  }

  get icon() {
    return 'iconoir-git-fork'
  }

  getEdgeErrorMessage(edge) {
    if (!edge.label.length) {
      return this.app.i18n.t('serviceType.coreRouterEdgeLabelRequired')
    } else if (!edge.condition.formula) {
      return this.app.i18n.t('serviceType.coreRouterEdgeConditionRequired')
    }
    return null
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }
    if (!service.edges?.length) {
      return this.app.i18n.t('serviceType.coreRouterEdgesRequired')
    }
    for (const edge of service.edges) {
      const errorMessage = this.getEdgeErrorMessage(edge)
      if (errorMessage) {
        return errorMessage
      }
    }
    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreRouterServiceForm
  }

  getOrder() {
    return 7
  }
}

export class CoreHTTPTriggerServiceType extends TriggerServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'http_trigger'
  }

  get name() {
    return this.app.i18n.t('serviceType.coreHTTPTrigger')
  }

  get description() {
    return this.app.i18n.t('serviceType.coreHTTPTriggerDescription')
  }

  get formComponent() {
    return CoreHTTPTriggerServiceForm
  }

  get icon() {
    return 'iconoir-globe'
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  getOrder() {
    return 8
  }
}

export class CoreIteratorServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'iterator'
  }

  get name() {
    return this.app.i18n.t('serviceType.coreIteration')
  }

  get description() {
    return this.app.i18n.t('serviceType.coreIterationDescription')
  }

  get icon() {
    return 'iconoir-repeat'
  }

  getErrorMessage({ service }) {
    if (!service?.source?.formula) {
      return this.app.i18n.t('serviceType.errorIterationSourceMissing')
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreIteratorServiceForm
  }

  getOrder() {
    return 5
  }
}

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

  get icon() {
    return 'iconoir-timer'
  }

  getDataSchema(service) {
    return service.schema
  }

  getErrorMessage({ service }) {
    if (!service?.interval) {
      return this.app.i18n.t('serviceType.corePeriodicErrorIntervalMissing')
    }
    return super.getErrorMessage({ service })
  }
}
