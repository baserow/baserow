import { Registerable } from '@baserow/modules/core/registry'

/**
 * Resolve feature eligibility, falling back to the generic model payload for
 * responses from an older application version during a rolling upgrade.
 *
 * @param {object|null} workspace The workspace with model availability.
 * @param {string} featureType The AI feature that consumes the models.
 * @returns {Object<string, string[]>} Available models grouped by provider type.
 */
export function getEnabledModelsForAIProviderFeature(workspace, featureType) {
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
