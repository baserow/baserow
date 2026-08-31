import { AIProviderModelFeatureType } from '@baserow/modules/core/aiProviderModelFeatureTypes'

export class AIAgentAIProviderModelFeatureType extends AIProviderModelFeatureType {
  static getType() {
    return 'ai_agent'
  }

  getName() {
    return this.$t('aiProviderModelFeature.aiAgent')
  }

  getDescription() {
    return this.$t('aiProviderModelFeature.aiAgentDescription')
  }
}
