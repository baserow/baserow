/** Crossing runtime boundaries needs the other entry's plugins and stores. */
export default defineNuxtRouteMiddleware((to) => {
  const app = useNuxtApp()
  // A fresh document already initializes its own plugins. Nuxt also runs route
  // middleware while rendering errors, whose route metadata may differ from the
  // original request; reloading there can turn a 404 into a redirect loop.
  if (import.meta.server || app.isHydrating || useError().value) return
  const applicationShell =
    app.$isWebFrontendHostname && to.meta.applicationShell !== false
  const authenticationPage =
    app.$isWebFrontendHostname && to.meta.authenticationPage === true
  if (
    applicationShell !== app.$isApplicationShell ||
    authenticationPage !== Boolean(app.$isAuthenticationPage)
  ) {
    return navigateTo(to.fullPath, { external: true })
  }
})
