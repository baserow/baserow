/**
 * Make sure only baserow routes are available for instance public hostname.
 */
export default defineNuxtPlugin({
  name: 'router',
  dependsOn: ['core', 'builder', 'database'],
  setup() {
    const router = useRouter()
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

    for (const r of router.getRoutes()) {
      if (isWebFrontendHostname) {
        if (r.meta?.publishedBuilderRoute && router.hasRoute(r.name)) {
          router.removeRoute(r.name)
        }
      } else {
        if (!r.meta?.publishedBuilderRoute && router.hasRoute(r.name)) {
          router.removeRoute(r.name)
        }
      }
    }
  },
})
