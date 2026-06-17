import {
  DataSourceServiceTypeMixin,
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
