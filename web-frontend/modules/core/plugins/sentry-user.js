import * as Sentry from '@sentry/nuxt'
import { useNuxtApp, useRuntimeConfig } from '#imports'

export default defineNuxtPlugin(() => {
  const runtimeConfig = useRuntimeConfig()

  if (!import.meta.client || !runtimeConfig.public.sentryDsn) return

  const nuxtApp = useNuxtApp()

  nuxtApp.hook('app:mounted', () => {
    nuxtApp.$store.subscribe((mutation) => {
      if (mutation.type === 'auth/SET_USER_DATA') {
        const userId = nuxtApp.$store.getters['auth/getUserId']
        if (userId) {
          Sentry.setUser({ id: String(userId) })
        }
      } else if (
        mutation.type === 'auth/LOGOFF' ||
        mutation.type === 'auth/CLEAR_USER_DATA'
      ) {
        Sentry.setUser(null)
      }
    })

    const userId = nuxtApp.$store.getters['auth/getUserId']
    if (userId) {
      Sentry.setUser({ id: String(userId) })
    }
  })
})
