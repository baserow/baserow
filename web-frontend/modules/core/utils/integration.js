/**
 * Returns the error message of the first of the given integrations that is in
 * error, so the places that list or depend on them (application sidebar,
 * settings, etc.) can point the user towards the integration that needs
 * attention.
 *
 * @param {object} app The Nuxt app, to resolve the integration types.
 * @param {Array} integrations The integrations to check.
 * @returns {string|null} The error message, or null if none are in error.
 */
export function integrationsErrorMessage(app, integrations) {
  for (const integration of integrations || []) {
    const message = app.$registry
      .get('integration', integration.type)
      .getErrorMessage(integration)
    if (message) {
      return message
    }
  }
  return null
}

/**
 * Returns the subtitle to show for an integration in a list: why it's in error
 * when it is, so the user knows what to fix, and its summary otherwise.
 *
 * @param {object} app The Nuxt app, to resolve the integration type.
 * @param {object} integration The integration to describe.
 * @returns {string} The subtitle.
 */
export function integrationSubtitle(app, integration) {
  const integrationType = app.$registry.get('integration', integration.type)
  return (
    integrationType.getErrorMessage(integration) ||
    integrationType.getSummary(integration)
  )
}

/**
 * Pick one available integration, preferring the application's own. Callers
 * supply integrations already filtered by type and permissions.
 */
export function getDefaultIntegration(integrations, application) {
  const own = integrations.filter(
    (integration) => integration.application_id === application.id
  )
  const candidates = own.length > 0 ? own : integrations
  return candidates.length === 1 ? candidates[0] : null
}
