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

    for (const r of router.getRoutes()) {
      if (frontendHostname === requestHostname) {
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
