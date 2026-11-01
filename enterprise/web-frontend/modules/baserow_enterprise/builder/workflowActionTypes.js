import { WorkflowActionServiceType } from '@baserow/modules/builder/workflowActionTypes'
import {
  CoreCodeServiceType,
  CoreXLSFileReaderServiceType,
} from '@baserow_enterprise/integrations/core/serviceTypes'

export class CoreCodeWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'code'
  }

  getErrorMessage(workflowAction, applicationContext) {
    if (applicationContext.builder?.untrusted_content) {
      return this.app.$i18n.t('builderUntrustedContent.warning')
    }
    return super.getErrorMessage(workflowAction, applicationContext)
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreCodeServiceType.getType())
  }

  getOrder() {
    return 65
  }
}

export class CoreXLSFileReaderWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'xls_file_reader'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      CoreXLSFileReaderServiceType.getType()
    )
  }

  getOrder() {
    return 80
  }
}
