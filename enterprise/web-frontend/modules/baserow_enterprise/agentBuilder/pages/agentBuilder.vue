<template>
  <AgentBuilderContent v-if="agentBuilder" :agent-builder="agentBuilder" />
</template>

<script setup>
import { computed } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import AgentBuilderContent from '@baserow_enterprise/agentBuilder/components/AgentBuilderContent'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'agentBuilderEnabled',
    'workspacesAndApplications',
    'selectAgentBuilder',
  ],
})

const { $store } = useNuxtApp()
const agentBuilder = computed(() => $store.getters['application/getSelected'])
useHead(() => ({ title: agentBuilder.value?.name }))

onBeforeRouteLeave((to) => {
  if (to.name !== 'agent-builder') {
    $store.dispatch('agentBuilderAgent/select', null)
  }
})
</script>
