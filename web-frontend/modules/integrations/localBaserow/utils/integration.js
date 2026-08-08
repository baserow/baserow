/**
 * The databases a Local Baserow integration reaches. Empty when none is chosen.
 */
export function databasesOfIntegration($store, application, integrationId) {
  const integration = $store.getters['integration/getIntegrationById'](
    application,
    integrationId
  )
  return integration?.context_data?.databases || []
}
