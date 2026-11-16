import { useRouter } from '#imports'

import {
  isStalePublishedIdError,
  isVisitorActionStaleError,
  reloadPublishedSite,
} from '@baserow/modules/builder/utils/error'

/**
 * The routes that render a published or previewed site. Other routes, like the
 * editor, use the same endpoints but must keep their own error handling.
 */
export const PUBLIC_SITE_ROUTE_NAMES = new Set([
  'application-builder-page',
  'application-builder-published',
  'application-builder-preview',
])

/**
 * When a request of a public site fails because the site has been published again
 * while the tab was open, reloads the current route to get the new version. This
 * covers every request of the site (pages, elements, data sources, workflow
 * actions, login...), so callers don't each need to handle it.
 *
 * The returned promise never settles when the reload happens, so the caller
 * doesn't show an error toast or a blank page while the browser leaves the page.
 * When the request came from something the visitor did, the reloaded page tells
 * them to try again.
 */
export const makeStalePublishedSiteInterceptor = (router, reload) => {
  return (error) => {
    const route = router.currentRoute.value
    if (
      import.meta.client &&
      PUBLIC_SITE_ROUTE_NAMES.has(route?.name) &&
      isStalePublishedIdError(error) &&
      reload(route.fullPath, { notify: isVisitorActionStaleError(error) })
    ) {
      return new Promise(() => {})
    }
    return Promise.reject(error)
  }
}

export default defineNuxtPlugin({
  name: 'builder-published-site-client-handler',
  dependsOn: ['client-handler'],
  setup(nuxtApp) {
    nuxtApp.$client.interceptors.response.use(
      null,
      makeStalePublishedSiteInterceptor(useRouter(), reloadPublishedSite)
    )
  },
})
