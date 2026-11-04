/** Crossing runtime boundaries needs the other entry's plugins and stores. */
export default defineNuxtRouteMiddleware((to) => {
  const app = useNuxtApp()
  const applicationShell =
    app.$isWebFrontendHostname && to.meta.applicationShell !== false
  if (applicationShell !== app.$isApplicationShell) {
    return navigateTo(to.fullPath, { external: true })
  }
})
