import { AIProviderModelFeatureType } from '@baserow/modules/core/aiProviderModelFeatureTypes'

export class AIAgentAIProviderModelFeatureType extends AIProviderModelFeatureType {
  /**
   * @returns {string} The eligibility identifier shared with the backend.
   */
  static getType() {
    return 'ai_agent'
  }

  /**
   * @returns {string} The localized feature name used in provider settings.
   */
  getName() {
    return this.$t('aiProviderModelFeature.aiAgent')
  }

  /**
   * @returns {string} The localized description of AI Agent eligibility.
   */
  getDescription() {
    return this.$t('aiProviderModelFeature.aiAgentDescription')
  }
}
