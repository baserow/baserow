/** Identify the application shell before feature plugins register their UI. */
export default defineNuxtPlugin({
  name: 'application-shell',
  dependsOn: ['nuxt:router', 'is-web-frontend-hostname'],
  setup(nuxtApp) {
    const url = useRequestURL()
    const route = nuxtApp.$router.resolve(url.pathname)
    return {
      provide: {
        isApplicationShell:
          nuxtApp.$isWebFrontendHostname &&
          route.meta.applicationShell !== false,
      },
    }
  },
})
