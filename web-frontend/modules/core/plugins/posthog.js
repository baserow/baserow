/*// eslint-disable-next-line import/no-named-as-default
import posthog from 'posthog-js'
import Vue from 'vue'

export default function ({ app: { router, $config, store } }, inject) {
  const projectApiKey = $config.POSTHOG_PROJECT_API_KEY
  const host = $config.POSTHOG_HOST

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

  inject('posthog', posthog)

  router.afterEach((to) => {
    Vue.nextTick(() => {
      const isAuthenticated = store.getters['auth/isAuthenticated']
      const userId = store.getters['auth/getUserId']
      const userEmail = store.getters['auth/getUsername']

      // Check if the user identification on every page route because they could
      // have changed accounts. This keeps the Posthog code isolated from the
      // authenticated system.
      if (
        isAuthenticated &&
        userId &&
        userId.toString() !== posthog.get_distinct_id()
      ) {
        posthog.identify(userId, { user_email: userEmail })
      }

      // Some pages must not be tracked like the ones that can expose a sensitive token.
      const preventTracking = !!to.meta.preventPageViewTracking
      if (preventTracking) {
        return
      }

      // Note: this might also be a good place to call posthog.register(...) in
      // order to update your properties on each page view
      posthog.capture('$pageview', {
        $current_url: `${window.location.origin}${to.fullPath}`,
      })
    })
  })
}
*/

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
