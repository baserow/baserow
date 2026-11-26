import { isWebFrontendHostname } from '@baserow/modules/core/utils/publishedSite'

/**
 * Whether the current hostname is a webfrontend hostname or not...
 */
export default defineNuxtPlugin({
  name: 'is-web-frontend-hostname',
  setup() {
    const runtimeConfig = useRuntimeConfig()

    // SSR-safe host detection
    const requestHostname = useRequestURL().hostname

    // Check if request hostname matches main hostname or any extra hostname so we know
    // whether the tool or a published application must be served.
    return {
      provide: {
        isWebFrontendHostname: isWebFrontendHostname(
          requestHostname,
          runtimeConfig.public
        ),
      },
    }
  },
})
