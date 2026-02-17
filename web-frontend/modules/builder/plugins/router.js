/**
 * Make sure only baserow routes are available for instance public hostname.
 */
export default defineNuxtPlugin({
  name: 'router',
  dependsOn: [
    'is-web-frontend-hostname',
    'core',
    'builder',
    'database',
    'automation',
    'dashboard',
    // Should execute after other applications are loaded to remove all the
    // unnecessary routes
  ],

  setup(nuxtApp) {
    const router = useRouter()
    const { $isWebFrontendHostname } = nuxtApp

    // Ensure only published routes are available if this is a published hostname
    for (const r of router.getRoutes()) {
      if ($isWebFrontendHostname) {
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
