import { inject } from 'vue'
import { useNuxtApp } from '#imports'

/**
 * Where the agent components read their state from and whether anything may
 * be changed. The template preview provides a store prefix so its data never
 * touches the stores of an agent the user has open, and marks itself as a
 * template: nothing may be edited or run there, whatever the user's role.
 */
export const STORE_PREFIX_KEY = 'agentStorePrefix'
export const TEMPLATE_KEY = 'agentTemplate'

export function useAgentContext() {
  const storePrefix = inject(STORE_PREFIX_KEY, '')
  const template = inject(TEMPLATE_KEY, false)
  const { $hasPermission } = useNuxtApp()
  const hasPermission = (...args) => !template && $hasPermission(...args)
  return { storePrefix, template, hasPermission }
}

export const AgentContextMixin = {
  inject: {
    storePrefix: { from: STORE_PREFIX_KEY, default: '' },
    agentTemplate: { from: TEMPLATE_KEY, default: false },
  },
  methods: {
    hasAgentPermission(...args) {
      return !this.agentTemplate && this.$hasPermission(...args)
    },
  },
}
