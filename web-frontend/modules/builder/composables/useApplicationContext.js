import { inject, provide, computed, unref } from 'vue'

export function useApplicationContext(props) {
  // Inject parent context (same behavior as the mixin)
  const injectedApplicationContext = inject('applicationContext', {})

  // Create the merged application context
  const applicationContext = computed(() => ({
    ...unref(injectedApplicationContext),
    ...(unref(props.applicationContextAdditions) ?? {}),
  }))

  // Provide the merged context to descendants
  provide('applicationContext', applicationContext)

  return {
    applicationContext,
  }
}
