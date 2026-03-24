import * as Sentry from '@sentry/nuxt'
import { nextTick } from 'vue'
import { useNuxtApp, useRouter, useRuntimeConfig } from '#imports'

export default defineNuxtPlugin(() => {
  const runtimeConfig = useRuntimeConfig()

  if (!import.meta.client || !runtimeConfig.public.sentryDsn) return

  const router = useRouter()
  const nuxtApp = useNuxtApp()

  router.afterEach(() => {
    nextTick(() => {
      const isAuthenticated = nuxtApp.$store.getters['auth/isAuthenticated']
      const userId = nuxtApp.$store.getters['auth/getUserId']

      if (isAuthenticated && userId) {
        Sentry.setUser({ id: String(userId) })
      } else {
        Sentry.setUser(null)
      }
    })
  })
})
