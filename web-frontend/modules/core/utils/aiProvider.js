/**
 * Extract the user facing message of an AI provider API error.
 *
 * The backend spells out which model an AI feature still resolves through, so
 * that detail is preferred over the generic fallback the caller provides.
 */
export function aiProviderErrorMessage(error, fallbackMessage = '') {
  const detail = error.response?.data?.detail
  return detail?.message || detail || fallbackMessage
}

/**
 * Name one AI feature the way its own module spells it.
 *
 * @param {Object} registry The application registry.
 * @param {string} featureType The registered feature identifier.
 * @returns {string} The feature display name, or the raw type when the feature
 *   is not loaded in this installation.
 */
export function aiProviderFeatureName(registry, featureType) {
  return registry.exists('aiProviderModelFeature', featureType)
    ? registry.get('aiProviderModelFeature', featureType).getName()
    : featureType
}

/**
 * Prefix a confirmation description with what still depends on a model.
 *
 * @param {{usage: Array<{featureType: string, count: number}>,
 *   blockingFeatureTypes: string[]}} result The model usage lookup.
 * @param {string} description The action description shown after the counts.
 * @param {Function} $t The translation function of the calling component.
 * @param {Object} registry The application registry.
 * @returns {string} The description, prefixed with the dependants.
 */
export function aiProviderModelUsageMessage(result, description, $t, registry) {
  const used = result.usage.filter((entry) => entry.count > 0)
  const sentences = []
  if (used.length > 0) {
    sentences.push(
      $t('aiProviderAdmin.modelInUse', {
        features: used
          .map((entry) =>
            $t('aiProviderAdmin.modelUsageFeature', {
              count: entry.count,
              feature: aiProviderFeatureName(registry, entry.featureType),
            })
          )
          .join(', '),
        count: used.reduce((total, entry) => total + entry.count, 0),
      })
    )
  }
  if (result.blockingFeatureTypes.length > 0) {
    sentences.push(
      $t('aiProviderAdmin.modelBlockedByFeature', {
        features: result.blockingFeatureTypes
          .map((featureType) => aiProviderFeatureName(registry, featureType))
          .join(', '),
      })
    )
  }
  return [...sentences, description].join(' ')
}
