import { WorkflowActionServiceType } from '@baserow/modules/builder/workflowActionTypes'
import { CoreCodeServiceType } from '@baserow_enterprise/integrations/core/serviceTypes'

export class CoreCodeWorkflowActionType extends WorkflowActionServiceType {
  static getType() {
    return 'code'
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreCodeServiceType.getType())
  }

  getOrder() {
    return 9
  }
}
