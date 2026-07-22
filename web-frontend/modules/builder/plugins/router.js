/**
 * Make sure only baserow routes are available for instance public hostname.
 */
export const shouldRemoveRoute = (
  route,
  { isWebFrontendHostname, isBuilderPreviewHostname, isBuilderPreviewRequest }
) => {
  if (isWebFrontendHostname) {
    const isPreviewRouteOnAnotherHost =
      route.meta?.previewBuilderRoute && !isBuilderPreviewRequest
    return route.meta?.publishedBuilderRoute || isPreviewRouteOnAnotherHost
  }

  if (isBuilderPreviewHostname) {
    return !route.meta?.previewBuilderRoute
  }

  return !route.meta?.publishedBuilderRoute
}

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
    const isBuilderPreviewPath =
      requestUrl.pathname === '/builder-preview' ||
      requestUrl.pathname.startsWith('/builder-preview/')
    const isBuilderPreviewRequest =
      isBuilderPreviewHostname || isBuilderPreviewPath

    // Ensure only routes for the current hostname role are available.
    for (const r of router.getRoutes()) {
      if (
        shouldRemoveRoute(r, {
          isWebFrontendHostname: $isWebFrontendHostname,
          isBuilderPreviewHostname,
          isBuilderPreviewRequest,
        }) &&
        router.hasRoute(r.name)
      ) {
        router.removeRoute(r.name)
      }
    }
  },
})
