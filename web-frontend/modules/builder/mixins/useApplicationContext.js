import { inject, provide, computed } from '@nuxtjs/composition-api'

export function useApplicationContext(applicationContextAdditions) {
  const injectedApplicationContext = inject('applicationContext')

  const applicationContext = computed(() => ({
    ...injectedApplicationContext,
    ...(applicationContextAdditions || {}),
  }))

  provide('applicationContext', applicationContext)

  return applicationContext
}
