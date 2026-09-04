/**
 * Resolve the AI Agent models shown by the client using the same precedence as
 * the backend.
 *
 * A complete integration override owns its connection and model list. A
 * partial override can only narrow the feature-filtered workspace list; it
 * cannot introduce a model which will later be rejected at dispatch.
 */
export function getEffectiveAIAgentModels({
  workspaceModels = [],
  integrationSettings = null,
  modelType = null,
}) {
  if (!integrationSettings || typeof integrationSettings !== 'object') {
    return workspaceModels
  }

  const integrationModels = Array.isArray(integrationSettings.models)
    ? integrationSettings.models
    : []

  if (modelType?.isIntegrationSettingsComplete(integrationSettings)) {
    return integrationModels
  }

  if (!Object.prototype.hasOwnProperty.call(integrationSettings, 'models')) {
    return workspaceModels
  }

  const enabledModels = new Set(workspaceModels)
  return integrationModels.filter((model) => enabledModels.has(model))
}
