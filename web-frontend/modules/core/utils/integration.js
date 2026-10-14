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
 * Returns whether one or more of the given integrations are in error, so the
 * places that list or depend on them (application sidebar, settings, etc.)
 * can point the user towards the integration that needs attention.
 *
 * @param {object} app The Nuxt app, to resolve the integration types.
 * @param {Array} integrations The integrations to check.
 * @returns {boolean} If any of the integrations are in error.
 */
export function integrationsInError(app, integrations) {
  if (!showIntegrationErrors(app)) {
    return false
  }
  return (integrations || []).some((integration) =>
    app.$registry.get('integration', integration.type).isInError(integration)
  )
}
