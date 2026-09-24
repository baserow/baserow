import { Registerable } from '@baserow/modules/core/registry'

export function getEnabledModelsForAIProviderFeature(
  workspace,
  featureType,
  featureFilteringEnabled = true
) {
  if (!featureFilteringEnabled) {
    return workspace?.generative_ai_models_enabled ?? {}
  }
  return (
    workspace?.ai_features?.[featureType]?.models ??
    workspace?.generative_ai_models_enabled ??
    {}
  )
}

export class AIProviderModelFeatureType extends Registerable {
  getName() {
    throw new Error(
      'Must be implemented by the AI provider model feature type.'
    )
  }

  getDescription() {
    return ''
  }

  /**
   * Whether this feature can fall back to a model configured through an
   * environment variable when nothing is selected in the database.
   */
  supportsLegacyModel() {
    return false
  }

  /**
   * The environment-variable model this feature falls back to, empty when none
   * is configured.
   */
  getLegacyModel() {
    return ''
  }
}
