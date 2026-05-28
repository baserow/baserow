import { WorkflowActionServiceType } from '@baserow/modules/builder/workflowActionTypes'
import { CoreCodeServiceType } from '@baserow_enterprise/integrations/core/serviceTypes'
import EnterpriseFeaturesObject from '@baserow_enterprise/features'

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

  isDeactivatedReason({ workspace }) {
    if (
      !this.app.$hasFeature(EnterpriseFeaturesObject.CODE_RUNNER, workspace.id)
    ) {
      return this.app.$i18n.t('enterprise.deactivated')
    }
    return super.isDeactivatedReason({ workspace })
  }
}
