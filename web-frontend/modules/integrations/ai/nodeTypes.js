import { NodeType } from '@baserow/modules/automation/nodeTypes'
import { ActionNodeTypeMixin } from '@baserow/modules/automation/nodeTypeMixins'
import { AIAgentServiceType } from '@baserow/modules/integrations/ai/serviceTypes'

export class AIAgentActionNodeType extends ActionNodeTypeMixin(NodeType) {
  static getType() {
    return 'ai_agent'
  }

  get name() {
    return this.app.i18n.t('nodeType.aiAgent')
  }

  get iconClass() {
    return 'iconoir-sparks'
  }

  get serviceType() {
    return this.app.$registry.get('service', AIAgentServiceType.getType())
  }

  getOrder() {
    return 8
  }
}
