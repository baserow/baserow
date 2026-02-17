/**
 * Whether the current hostname is a webfrontend hostname or not...
 */
export default defineNuxtPlugin({
  name: 'is-web-frontend-hostname',
  setup() {
    const runtimeConfig = useRuntimeConfig()

    // SSR-safe host detection
    const requestHostname = useRequestURL().hostname

    const frontendHostname = new URL(runtimeConfig.public.publicWebFrontendUrl)
      .hostname

    const extraPublicHostnames =
      runtimeConfig.public.extraPublicWebFrontendHostnames || []

    // Check if request hostname matches main hostname or any extra hostname so we know
    // whether the tool or a published application must be served.
    const isWebFrontendHostname =
      frontendHostname === requestHostname ||
      extraPublicHostnames.includes(requestHostname)

    return { provide: { isWebFrontendHostname } }
  },
})
