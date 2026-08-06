/**
 * The databases a Local Baserow integration reaches, which is where a service
 * rendered under it picks its table from.
 *
 * @param $store - The Vuex store.
 * @param application - The application the integration belongs to.
 * @param integrationId - The chosen integration, if any.
 * @returns The databases, empty when nothing is chosen yet.
 */
export function databasesOfIntegration($store, application, integrationId) {
  const integration = $store.getters['integration/getIntegrationById'](
    application,
    integrationId
  )
  return integration?.context_data?.databases || []
}
