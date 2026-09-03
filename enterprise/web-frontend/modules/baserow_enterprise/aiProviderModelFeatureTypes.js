import { AIProviderModelFeatureType } from '@baserow/modules/core/aiProviderModelFeatureTypes'

export class KumaAIProviderModelFeatureType extends AIProviderModelFeatureType {
  static getType() {
    return 'kuma'
  }

  getName() {
    return this.$t('aiProviderModelFeature.kuma')
  }

  getDescription() {
    return this.$t('aiProviderModelFeature.kumaDescription')
  }

  getOrder() {
    return 20
  }

  supportsLegacyModel() {
    return true
  }

  getLegacyModel() {
    return this.app.$config.public.baserowEnterpriseAssistantLlmModel || ''
  }
}
