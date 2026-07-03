import CoreHTTPTriggerServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPTriggerServiceForm'
import {
  DataSourceServiceTypeMixin,
  ServiceType,
  TriggerServiceTypeMixin,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import CoreHTTPRequestServiceForm from '@baserow/modules/integrations/core/components/services/CoreHTTPRequestServiceForm'
import CoreSMTPEmailServiceForm from '@baserow/modules/integrations/core/components/services/CoreSMTPEmailServiceForm'
import CoreRouterServiceForm from '@baserow/modules/integrations/core/components/services/CoreRouterServiceForm'
import CoreGotoServiceForm from '@baserow/modules/automation/components/services/CoreGotoServiceForm'
import CoreIteratorServiceForm from '@baserow/modules/integrations/core/components/services/CoreIteratorServiceForm'
import CoreCSVFileReaderServiceForm from '@baserow/modules/integrations/core/components/services/CoreCSVFileReaderServiceForm'
import CorePeriodicServiceForm from '@baserow/modules/integrations/core/components/services/CorePeriodicServiceForm.vue'
import CoreStartWorkflowServiceForm from '@baserow/modules/integrations/core/components/services/CoreStartWorkflowServiceForm.vue'

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
    return this.app.$i18n.t('serviceType.coreHTTPRequest')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreHTTPRequestDescription')
  }

  getErrorMessage({ service }) {
    // We check undefined because the url is not returned in public mode the
    // property is just ignored
    if (
      service !== undefined &&
      service.url !== undefined &&
      !service.url.formula
    ) {
      return this.app.$i18n.t('serviceType.errorUrlMissing')
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
    return this.app.$i18n.t('serviceType.coreSMTPEmail')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreSMTPEmailDescription')
  }

  get icon() {
    return 'iconoir-send-mail'
  }

  getErrorMessage({ service }) {
    if (
      service === undefined ||
      // This case happens in a published application. We don't want to check
      // the validity in that case.
      service.use_instance_smtp_settings === undefined
    ) {
      return null
    }

    if (!service.use_instance_smtp_settings && !service.integration_id) {
      return this.app.$i18n.t('serviceType.errorNoIntegrationSelected')
    }

    if (
      !service.use_instance_smtp_settings &&
      service.from_email !== undefined &&
      !service.from_email.formula
    ) {
      return this.app.$i18n.t('serviceType.errorFromEmailMissing')
    }

    if (service.to_emails !== undefined && !service.to_emails.formula) {
      return this.app.$i18n.t('serviceType.errorToEmailsMissing')
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
    return this.app.$i18n.t('serviceType.coreRouter')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreRouterDescription')
  }

  get icon() {
    return 'iconoir-git-fork'
  }

  getEdgeErrorMessage(edge) {
    if (!edge.label.length) {
      return this.app.$i18n.t('serviceType.coreRouterEdgeLabelRequired')
    } else if (!edge.condition.formula) {
      return this.app.$i18n.t('serviceType.coreRouterEdgeConditionRequired')
    }
    return null
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }
    if (!service.edges?.length) {
      return this.app.$i18n.t('serviceType.coreRouterEdgesRequired')
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

export class CoreGotoServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'goto'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreGoto')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreGotoDescription')
  }

  get icon() {
    return 'iconoir-long-arrow-up-right'
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }
    if (!service.destination_node_id) {
      return this.app.$i18n.t('serviceType.coreGotoDestinationRequired')
    }
    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreGotoServiceForm
  }

  getOrder() {
    return 10
  }
}

export class CoreHTTPTriggerServiceType extends TriggerServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'http_trigger'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreHTTPTrigger')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreHTTPTriggerDescription')
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

export class CoreManualTriggerServiceType extends TriggerServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'manual'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreManualTrigger')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreManualTriggerDescription')
  }

  get icon() {
    return 'iconoir-play'
  }

  canBeImmediatelyDispatched(service) {
    return true
  }

  getDataSchema(service) {
    return service.schema
  }

  getOrder() {
    return 9
  }
}

export class CoreIteratorServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'iterator'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreIteration')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreIterationDescription')
  }

  get icon() {
    return 'iconoir-repeat'
  }

  get returnsList() {
    return true
  }

  getErrorMessage({ service }) {
    if (!service?.source?.formula) {
      return this.app.$i18n.t('serviceType.errorIterationSourceMissing')
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

export class CoreCSVFileReaderServiceType extends DataSourceServiceTypeMixin(
  WorkflowActionServiceTypeMixin(ServiceType)
) {
  static getType() {
    return 'csv_file_reader'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreCSVFileReader')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreCSVFileReaderDescription')
  }

  get icon() {
    return 'iconoir-page'
  }

  get returnsList() {
    return true
  }

  getRecordName(service, record) {
    return record?.name || record?.id || ''
  }

  getIdProperty(service, record) {
    return record?.id || record?._id
  }

  getResult(service, data) {
    return data.results
  }

  getErrorMessage({ service }) {
    if (service?.input_type === undefined && service?.file === undefined) {
      // The service is not loaded yet, or we are in preview or published mode
      return super.getErrorMessage({ service })
    }

    if (service?.input_type === 'content') {
      if (!service?.csv?.formula) {
        return this.app.$i18n.t('serviceType.errorCSVContentMissing')
      }
    } else if (!service?.file?.formula) {
      return this.app.$i18n.t('serviceType.errorCSVFileMissing')
    }

    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreCSVFileReaderServiceForm
  }

  getOrder() {
    return 6
  }
}

export class CoreStartWorkflowServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'start_workflow'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreStartWorkflow')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreStartWorkflowDescription')
  }

  get icon() {
    return 'iconoir-play'
  }

  getWorkflow(workflowId) {
    const workspace = this.app.$store.getters['workspace/getSelected']

    if (!workspace?.id || !workflowId) {
      return null
    }

    const automations = this.app.$store.getters[
      'application/getAllOfWorkspace'
    ](workspace).filter((application) => application.type === 'automation')

    return automations
      .flatMap((automation) =>
        this.app.$store.getters['automationWorkflow/getWorkflows'](automation)
      )
      .find((workflow) => workflow.id === workflowId)
  }

  getErrorMessage({ service }) {
    if (service !== undefined && service.workflow_id === null) {
      return this.app.$i18n.t('serviceType.errorNoWorkflowSelected')
    }

    const workflow = this.getWorkflow(service?.workflow_id)
    if (workflow && !workflow.immediate_dispatch) {
      return this.app.$i18n.t('serviceType.errorWorkflowNotImmediateDispatch')
    }

    return super.getErrorMessage({ service })
  }

  get formComponent() {
    return CoreStartWorkflowServiceForm
  }

  getDataSchema(service) {
    return service.schema
  }

  getOrder() {
    return 8
  }
}

export class PeriodicTriggerServiceType extends TriggerServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'periodic'
  }

  get name() {
    return this.app.$i18n.t('serviceType.corePeriodic')
  }

  get description() {
    return this.app.$i18n.t('serviceType.corePeriodicDescription')
  }

  get formComponent() {
    return CorePeriodicServiceForm
  }

  get icon() {
    return 'iconoir-timer'
  }

  canBeImmediatelyDispatched(service) {
    return true
  }

  getDataSchema(service) {
    return service.schema
  }

  getErrorMessage({ service }) {
    if (!service?.interval) {
      return this.app.$i18n.t('serviceType.corePeriodicErrorIntervalMissing')
    }
    return super.getErrorMessage({ service })
  }
}
