import {
  DataSourceServiceTypeMixin,
  getFilesGroup,
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import EnterpriseFeaturesObject from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import {
  CodeRunnerPaidFeature,
  XLSFileReaderPaidFeature,
} from '@baserow_enterprise/paidFeatures'
import CoreCodeServiceForm from '@baserow_enterprise/integrations/core/components/services/CoreCodeServiceForm.vue'
import CoreXLSFileReaderServiceForm from '@baserow_enterprise/integrations/core/components/services/CoreXLSFileReaderServiceForm.vue'
import { LocalBaserowIntegrationType } from '@baserow/modules/integrations/localBaserow/integrationTypes'
import CoreRunAgentServiceForm from '@baserow_enterprise/integrations/core/components/services/CoreRunAgentServiceForm.vue'

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

  isDeactivatedReason({ workspace }) {
    if (!workspace) {
      return null
    }
    if (
      !this.app.$hasFeature(EnterpriseFeaturesObject.CODE_RUNNER, workspace.id)
    ) {
      return this.app.$i18n.t('enterprise.deactivated')
    }
    return null
  }

  getDeactivatedClickModal({ workspace }) {
    if (
      workspace &&
      !this.app.$hasFeature(EnterpriseFeaturesObject.CODE_RUNNER, workspace.id)
    ) {
      return [
        PaidFeaturesModal,
        { 'initial-selected-type': CodeRunnerPaidFeature.getType() },
      ]
    }
    return null
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

export class CoreXLSFileReaderServiceType extends DataSourceServiceTypeMixin(
  WorkflowActionServiceTypeMixin(ServiceType)
) {
  static getType() {
    return 'xls_file_reader'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreXLSFileReader')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreXLSFileReaderDescription')
  }

  get icon() {
    return 'iconoir-page'
  }

  get group() {
    return getFilesGroup(this.app)
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
    if (service?.file !== undefined && !service?.file?.formula) {
      return this.app.$i18n.t('serviceType.errorXLSFileMissing')
    }

    return super.getErrorMessage({ service })
  }

  isDeactivatedReason({ workspace }) {
    if (!workspace) {
      return null
    }
    if (
      !this.app.$hasFeature(
        EnterpriseFeaturesObject.XLS_FILE_READER,
        workspace.id
      )
    ) {
      return this.app.$i18n.t('enterprise.deactivated')
    }
    return null
  }

  getDeactivatedClickModal({ workspace }) {
    if (
      workspace &&
      !this.app.$hasFeature(
        EnterpriseFeaturesObject.XLS_FILE_READER,
        workspace.id
      )
    ) {
      return [
        PaidFeaturesModal,
        { 'initial-selected-type': XLSFileReaderPaidFeature.getType() },
      ]
    }
    return null
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return CoreXLSFileReaderServiceForm
  }

  getOrder() {
    return 7
  }
}

/**
 * Starts a conversation with an agent application. One service for every
 * host: a button field, an automation node, an application builder action
 * and, as an action tool, another agent.
 */
export class CoreRunAgentServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'run_agent'
  }

  get name() {
    return this.app.$i18n.t('serviceType.coreRunAgent')
  }

  get description() {
    return this.app.$i18n.t('serviceType.coreRunAgentDescription')
  }

  get icon() {
    return 'baserow-icon-agent'
  }

  /**
   * Listed with the Local Baserow services: an agent is part of the workspace,
   * not an external workflow. The group is built by hand because the service
   * itself needs no integration, and declaring one would add the integration
   * picker to its form.
   */
  get group() {
    const integrationType = this.app.$registry.get(
      'integration',
      LocalBaserowIntegrationType.getType()
    )
    return {
      id: `integration-${integrationType.getType()}`,
      label: integrationType.name,
      image: integrationType.image,
      icon: integrationType.iconClass,
      iconColor: integrationType.iconColor,
    }
  }

  getAgentApplication(
    applicationId,
    workspace = this.app.$store.getters['workspace/getSelected']
  ) {
    if (!workspace?.id || !applicationId) {
      return null
    }
    return this.app.$store.getters['application/getAllOfWorkspace'](
      workspace
    ).find(
      (application) =>
        application.type === 'agent' && application.id === applicationId
    )
  }

  getErrorMessage({ service }) {
    if (service !== undefined && !service.agent_application_id) {
      return this.app.$i18n.t('serviceType.errorNoAgentSelected')
    }
    // An empty store looks like a missing agent until applications loaded.
    if (
      service?.agent_application_id &&
      this.app.$store.getters['application/isLoaded'] &&
      !this.getAgentApplication(service.agent_application_id)
    ) {
      return this.app.$i18n.t('serviceType.errorAgentMissing')
    }
    return super.getErrorMessage({ service })
  }

  get formComponent() {
    return CoreRunAgentServiceForm
  }

  getDataSchema(applicationContext, service) {
    return service?.schema || null
  }

  getOrder() {
    return 9
  }
}
