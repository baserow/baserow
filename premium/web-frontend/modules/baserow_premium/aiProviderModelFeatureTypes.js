import { AIProviderModelFeatureType } from '@baserow/modules/core/aiProviderModelFeatureTypes'

export class AIFieldsAIProviderModelFeatureType extends AIProviderModelFeatureType {
  static getType() {
    return 'ai_fields'
  }

  getName() {
    return this.$t('aiProviderModelFeature.aiFields')
  }

  getDescription() {
    return this.$t('aiProviderModelFeature.aiFieldsDescription')
  }
}
