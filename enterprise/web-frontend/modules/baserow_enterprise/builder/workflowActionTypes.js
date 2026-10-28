import { WorkflowActionServiceType } from '@baserow/modules/builder/workflowActionTypes'
import {
  CoreCodeServiceType,
  CoreXLSFileReaderServiceType,
} from '@baserow_enterprise/integrations/core/serviceTypes'
import { LocalBaserowSemanticSearchServiceType } from '@baserow_enterprise/integrations/localBaserow/serviceTypes'

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

export class LocalBaserowSemanticSearchWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'local_baserow_semantic_search'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowSemanticSearchServiceType.getType()
    )
  }

  getOrder() {
    return 45.5
  }
}
