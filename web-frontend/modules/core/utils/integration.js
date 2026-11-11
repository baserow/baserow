import { FF_APPLICATION_IN_ERROR } from '@baserow/modules/core/plugins/featureFlags'

/**
 * Returns whether the errors of integrations should be shown to the user, by
 * flagging them and the places that lead to them (application sidebar,
 * settings, etc.).
 *
 * @param {object} app The Nuxt app.
 * @returns {boolean} If integration errors should be surfaced.
 */
export function showIntegrationErrors(app) {
  return app.$featureFlagIsEnabled(FF_APPLICATION_IN_ERROR)
}

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
  if (!showIntegrationErrors(app)) {
    return null
  }
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
    (showIntegrationErrors(app) &&
      integrationType.getErrorMessage(integration)) ||
    integrationType.getSummary(integration)
  )
}
