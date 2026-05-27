import { NodeType } from '@baserow/modules/automation/nodeTypes'
import { ActionNodeTypeMixin } from '@baserow/modules/automation/nodeTypeMixins'
import { CoreCodeServiceType } from '@baserow_enterprise/integrations/core/serviceTypes'

export class CoreCodeNodeType extends ActionNodeTypeMixin(NodeType) {
  static getType() {
    return 'code'
  }

  getOrder() {
    return 6
  }

  get name() {
    return this.app.$i18n.t('nodeType.codeLabel')
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreCodeServiceType.getType())
  }
}
