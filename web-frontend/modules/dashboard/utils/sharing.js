import DashboardService from '@baserow/modules/dashboard/services/dashboard'

/**
 * The sharing state of a dashboard as the application endpoints return it.
 */
export const DASHBOARD_SHARING_FIELDS = [
  'public',
  'slug',
  'public_has_password',
  'show_logo',
]

/**
 * Updates the sharing state of a dashboard through the dedicated sharing
 * endpoint and copies the state that the backend returns into the store. The
 * generic `application/update` action can't be used: the backend ignores the
 * sharing fields there, and it only copies the requested keys back, which isn't
 * enough here either because `public_password` is write only and a change of
 * `public` also clears the password, so the derived `public_has_password` has
 * to come from the response.
 *
 * @param {object} nuxtApp Anything exposing `$client` and `$store`, like the
 *  nuxt app or an options API component.
 * @param {object} dashboard The dashboard application in the store.
 * @param {object} values The sharing values to send, like `{ public: true }`.
 * @returns {object} The updated application as the backend returned it.
 */
export async function updateDashboardSharing(
  { $client, $store },
  dashboard,
  values
) {
  const { data } = await DashboardService($client).updateSharing(
    dashboard.id,
    values
  )
  const sharing = Object.fromEntries(
    DASHBOARD_SHARING_FIELDS.filter((field) => field in data).map((field) => [
      field,
      data[field],
    ])
  )
  await $store.dispatch('application/forceUpdate', {
    application: dashboard,
    data: sharing,
  })
  return data
}
