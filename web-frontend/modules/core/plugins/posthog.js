import { nextTick } from 'vue'
import {
  defineNuxtPlugin,
  useNuxtApp,
  useRouter,
  useRuntimeConfig,
} from '#imports'

export default defineNuxtPlugin(() => {
  const router = useRouter()
  const runtimeConfig = useRuntimeConfig()
  const nuxtApp = useNuxtApp()

  const projectApiKey = runtimeConfig.public.posthogProjectApiKey
  const host = runtimeConfig.public.posthogHost

  if (!import.meta.client || (!projectApiKey && !host)) {
    return
  }

  // Load configured analytics separately from the initial client bundle.
  import('posthog-js')
    .then(async ({ default: posthog }) => {
      posthog.init(projectApiKey, {
        api_host: host,
        capture_pageview: false,
        capture_pageleave: false,
        disable_session_recording: true,
        autocapture: {
          css_selector_allowlist: ['[ph-autocapture]'],
        },
      })

      nuxtApp.provide('posthog', posthog)

      const capturePageview = (to) => {
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

          const preventTracking = !!to.meta.preventPageViewTracking
          if (preventTracking) {
            return
          }

          posthog.capture('$pageview', {
            $current_url: `${window.location.origin}${to.fullPath}`,
          })
        })
      }

      let trackedNavigation = false
      router.afterEach((to, from, failure) => {
        if (failure) {
          return
        }
        trackedNavigation = true
        capturePageview(to)
      })

      // The initial navigation can finish before the SDK chunk has loaded. Wait
      // for it and capture the current route unless afterEach already handled it.
      await router.isReady()
      if (!trackedNavigation) {
        capturePageview(router.currentRoute.value)
      }
    })
    .catch((error) => {
      console.warn('Failed to initialize PostHog:', error)
    })
})
