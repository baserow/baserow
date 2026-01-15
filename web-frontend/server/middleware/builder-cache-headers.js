/**
 * This server middleware disables caching for Builder pages via
 * cache-control headers. We already perform caching at the API level.
 */
export default defineEventHandler((e) => {
  const host = getRequestHost(e)
  const config = useRuntimeConfig()
  const pathname = getRequestURL(e).pathname
  const hostname = new URL(config.public.publicWebFrontendUrl).hostname

  const isPublished = !host.startsWith(hostname)
  const isPreview = /^\/builder\/\d+\/preview/.test(pathname)

  if (isPublished || isPreview) {
    setResponseHeaders(e, {
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      Pragma: 'no-cache',
      Expires: '0',
    })
  }
})
