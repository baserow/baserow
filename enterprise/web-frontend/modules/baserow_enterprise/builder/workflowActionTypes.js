import { WorkflowActionServiceType } from '@baserow/modules/builder/workflowActionTypes'
import {
  CoreCodeServiceType,
  CoreRunAgentServiceType,
  CoreXLSFileReaderServiceType,
} from '@baserow_enterprise/integrations/core/serviceTypes'

export class CoreCodeWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'code'
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

export class CoreRunAgentWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'run_agent'
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreRunAgentServiceType.getType())
  }

  getOrder() {
    return 85
  }
}
