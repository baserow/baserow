import Router from 'vue-router'

import {
  createRouter as createDefaultRouter,
  routerOptions as defaultRouterOptions,
} from './defaultRouter'

/**
 * Replace the official Nuxt `createRouter` function. If the request hostname is equal
 * to the `PUBLIC_WEB_FRONTEND_URL` hostname, the router will contain only routes that
 * are not marked as `{ meta: { publishedBuilderRoute: true } }` and it will contains
 * only this routes otherwise.
 *
 * @param {*} ssrContext
 * @param {*} config
 * @returns the new router instance accessible from `this.$router` in components.
 */
export function createRouter(ssrContext, config) {
  let isWebFrontendHostname = true
  // On the server
  if (
    process.server &&
    ssrContext &&
    ssrContext.nuxt &&
    ssrContext.req &&
    ssrContext.runtimeConfig
  ) {
    const req = ssrContext.req
    const runtimeConfig = ssrContext.runtimeConfig
    const frontendHostname = new URL(
      runtimeConfig.public.PUBLIC_WEB_FRONTEND_URL
    ).hostname
    const requestHostname = new URL(`http://${req.headers.host}`).hostname
    const extraPublicHostnames =
      runtimeConfig.public.EXTRA_PUBLIC_WEB_FRONTEND_HOSTNAMES || []

    // Check if request hostname matches main hostname or any extra hostname so we know
    // whether the tool or a published application must be served.
    isWebFrontendHostname =
      frontendHostname === requestHostname ||
      extraPublicHostnames.includes(requestHostname)

    // Send the variable to the frontend using the `__NUXT__` property
    ssrContext.nuxt.isWebFrontendHostname = isWebFrontendHostname
  }

  // On the client
  if (
    process.client &&
    window.__NUXT__ &&
    window.__NUXT__.isWebFrontendHostname !== isWebFrontendHostname
  ) {
    isWebFrontendHostname = window.__NUXT__.isWebFrontendHostname
  }

  const routerOptions =
    defaultRouterOptions || createDefaultRouter(ssrContext, config).options

  // Filter the routes to keep only the core Baserow routes if the hostname is the
  // main one and for any other hostname, we keep the routes marked as
  // `publishedBuilderRoute`.
  const newRoutes = routerOptions.routes.filter((route) => {
    const isPublishedWebsiteRoute = !!route?.meta?.publishedBuilderRoute
    return (
      (isWebFrontendHostname && !isPublishedWebsiteRoute) ||
      (!isWebFrontendHostname && isPublishedWebsiteRoute)
    )
  })

  return new Router({
    ...routerOptions,
    routes: newRoutes,
  })
}
