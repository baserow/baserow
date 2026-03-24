import { Registerable } from '@baserow/modules/core/registry'

export class AIFeatureType extends Registerable {
  getName() {
    return this.type
  }

  getOrder() {
    return 50
  }
}

export class AIFieldFeatureType extends AIFeatureType {
  static getType() {
    return 'ai_field'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('aiFeatureType.aiField')
  }

  getOrder() {
    return 10
  }
}

export class AIAssistantFeatureType extends AIFeatureType {
  static getType() {
    return 'ai_assistant'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('aiFeatureType.aiAssistant')
  }

  getOrder() {
    return 20
  }
}

export class AIAgentNodeFeatureType extends AIFeatureType {
  static getType() {
    return 'ai_agent_node'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('aiFeatureType.aiAgentNode')
  }

  getOrder() {
    return 30
  }
}
