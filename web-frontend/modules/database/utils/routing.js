import { useNuxtApp } from '#app'

export const tableRouteResetViewIfNeeded = (
  params,
  name = 'database-table-row'
) => {
  const { $router } = useNuxtApp()
  const current = $router.currentRoute.value

  if (
    // We must always check for `database-table` route because this is the name of
    // the root route in `modules/database/routes.js`. Because the child routes show
    // a modal, it will never have that route name when navigating to another row.
    current.name === 'database-table' &&
    // If the table has changed, the viewId must not be remembered because that will
    // result in an error.
    `${current.params.tableId}` !== `${params.tableId}`
  ) {
    // Setting the viewId to an empty string makes sure the viewId is not remembered
    // when navigating to another row.
    params.viewId = ''
  }

  return {
    name,
    params,
  }
}
