/**
 * Unselect the current application if we are moving away from an application
 * context route (dashboard, database, builder, automation)
 */
export default defineNuxtRouteMiddleware((to) => {
  const { $store } = useNuxtApp()

  if (
    !to.meta.applicationContext &&
    $store.getters['application/getSelected']
  ) {
    $store.dispatch('application/unselect')
  }
})
