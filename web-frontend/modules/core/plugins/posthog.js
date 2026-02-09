import posthog from 'posthog-js'
import { nextTick } from 'vue'
import { useNuxtApp, useRouter, useRuntimeConfig } from '#imports'

export default defineNuxtPlugin(() => {
  const router = useRouter()
  const runtimeConfig = useRuntimeConfig()
  const nuxtApp = useNuxtApp()

  const projectApiKey = runtimeConfig.public.posthogProjectApiKey
  const host = runtimeConfig.public.posthogHost

  if (!import.meta.client || (!projectApiKey && !host)) {
    return
  }

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

      const preventTracking = !!to.meta.preventPageViewTracking
      if (preventTracking) {
        return
      }

      posthog.capture('$pageview', {
        $current_url: `${window.location.origin}${to.fullPath}`,
      })
    })
  })
})
