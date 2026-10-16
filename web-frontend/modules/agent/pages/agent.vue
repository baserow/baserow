<template>
  <AgentApplicationContent v-if="agent" :agent="agent" />
</template>

<script setup>
import { computed } from 'vue'
import AgentApplicationContent from '@baserow/modules/agent/components/AgentApplicationContent'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'selectAgentApplication',
  ],
})

const { $store } = useNuxtApp()
const agent = computed(() => {
  const selected = $store.getters['application/getSelected']
  return selected?.type === 'agent' ? selected : null
})
useHead(() => ({ title: agent.value?.name }))
</script>
