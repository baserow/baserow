import { nextTick } from 'vue'
import { useNuxtApp, useRouter, useRuntimeConfig } from '#imports'

import { carriesPrivateLinkToken } from '@baserow/modules/core/utils/templatePrivateLink'
import {
  getPosthogOptions,
  getPublishedPageViewProperties,
  isPublishedSite,
} from '@baserow/modules/core/utils/publishedSite'

export default defineNuxtPlugin({
  name: 'posthog',
  parallel: true,
  async setup() {
    const router = useRouter()
    const runtimeConfig = useRuntimeConfig()
    const nuxtApp = useNuxtApp()

    const projectApiKey = runtimeConfig.public.posthogProjectApiKey
    const host = runtimeConfig.public.posthogHost

    if (!import.meta.client || (!projectApiKey && !host)) {
      return
    }

    const publishedSite = isPublishedSite(
      window.location.hostname,
      runtimeConfig.public
    )

    const { default: posthog } = await import('posthog-js')
    posthog.init(projectApiKey, getPosthogOptions({ host, publishedSite }))

    if (publishedSite) {
      // A published application only reports its page views. The rest of the app
      // gets this function instead of `$posthog`, so nothing else can be captured.
      nuxtApp.provide('capturePublishedPageView', (page) => {
        posthog.capture(
          '$pageview',
          getPublishedPageViewProperties(window.location, page)
        )
      })
      return
    }

    nuxtApp.provide('posthog', posthog)

    router.afterEach((to) => {
      nextTick(() => {
        const isAuthenticated = nuxtApp.$store.getters['auth/isAuthenticated']
        const userId = nuxtApp.$store.getters['auth/getUserId']
        const userEmail = nuxtApp.$store.getters['auth/getUsername']

        if (
          isAuthenticated &&
          userId &&
          userId.toString() !== posthog.get_distinct_id()
        ) {
          posthog.identify(userId, { user_email: userEmail })
        }

        const preventTracking =
          !!to.meta.preventPageViewTracking ||
          carriesPrivateLinkToken(to.fullPath)
        if (preventTracking) {
          return
        }

        posthog.capture('$pageview', {
          $current_url: `${window.location.origin}${to.fullPath}`,
        })
      })
    })
  },
})
