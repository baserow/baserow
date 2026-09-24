/**
 * Resolve the AI Agent models shown by the client using the same precedence as
 * the backend.
 *
 * A complete integration override owns its connection. Built-in provider types
 * inherit the model allowlist when their override omits models; an explicit
 * list, including an empty one, remains authoritative. A partial override can
 * only narrow the feature-filtered workspace list.
 *
 * @param {object} options The inputs for one provider's model resolution.
 * @param {string[]} [options.workspaceModels=[]] Effective workspace models,
 *   already filtered for AI Agent eligibility when the provider flag is enabled.
 * @param {object|null} [options.integrationSettings=null] Provider settings from
 *   the selected integration.
 * @param {GenerativeAIModelType|null} [options.modelType=null] The registered
 *   provider type, or null when its extension is no longer installed.
 * @returns {string[]} The available model identifiers. Treat the returned list
 *   as read-only because it can be the original workspace or integration list.
 */
export function getEffectiveAIAgentModels({
  workspaceModels = [],
  integrationSettings = null,
  modelType = null,
}) {
  if (!modelType) {
    return []
  }

  if (!integrationSettings || typeof integrationSettings !== 'object') {
    return workspaceModels
  }

  const integrationModels = Array.isArray(integrationSettings.models)
    ? integrationSettings.models
    : []
  const hasModels = Object.prototype.hasOwnProperty.call(
    integrationSettings,
    'models'
  )

  if (modelType.isIntegrationSettingsComplete(integrationSettings)) {
    if (!hasModels && modelType.isBuiltInProviderType()) {
      return workspaceModels
    }
    return integrationModels
  }

  if (!hasModels) {
    return workspaceModels
  }

  const enabledModels = new Set(workspaceModels)
  return integrationModels.filter((model) => enabledModels.has(model))
}
