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
    const runtimeConfig = useRuntimeConfig()
    const { $isWebFrontendHostname } = nuxtApp
    const requestUrl = useRequestURL()
    const requestHostname = requestUrl.hostname
    const builderPreviewHostname = new URL(
      runtimeConfig.public.builderPreviewUrl
    ).hostname
    const isBuilderPreviewHostname = builderPreviewHostname === requestHostname
    const builderPreviewPathPrefix = `/${(
      runtimeConfig.public.builderPreviewPathPrefix || ''
    )
      .split('/')
      .filter(Boolean)
      .join('/')}`
    const isBuilderPreviewPath =
      builderPreviewPathPrefix !== '/' &&
      (requestUrl.pathname === builderPreviewPathPrefix ||
        requestUrl.pathname.startsWith(`${builderPreviewPathPrefix}/`))
    const isBuilderPreviewRequest =
      isBuilderPreviewHostname || isBuilderPreviewPath

    // Ensure only routes for the current hostname role are available.
    for (const r of router.getRoutes()) {
      if ($isWebFrontendHostname) {
        const isPreviewRouteOnAnotherHost =
          r.meta?.previewBuilderRoute && !isBuilderPreviewRequest
        if (
          (r.meta?.publishedBuilderRoute || isPreviewRouteOnAnotherHost) &&
          router.hasRoute(r.name)
        ) {
          router.removeRoute(r.name)
        }
      } else if (isBuilderPreviewHostname) {
        if (!r.meta?.previewBuilderRoute && router.hasRoute(r.name)) {
          router.removeRoute(r.name)
        }
      } else {
        if (
          (!r.meta?.publishedBuilderRoute || r.meta?.previewBuilderRoute) &&
          router.hasRoute(r.name)
        ) {
          router.removeRoute(r.name)
        }
      }
    }
  },
})
