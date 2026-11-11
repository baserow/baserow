<template>
  <AgentApplicationContent v-if="agent" :agent="agent" />
</template>

<script setup>
import { AGENT_APPLICATION_TYPE } from '@baserow/modules/agent/constants'
import { computed } from 'vue'
import { createError } from '#app'
import AgentApplicationContent from '@baserow/modules/agent/components/AgentApplicationContent'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import { usePageAsyncData } from '@baserow/modules/core/composables/usePageAsyncData'
import { normalizeError } from '@baserow/modules/database/utils/errors'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'selectAgentApplication',
  ],
})

const { $store, $client } = useNuxtApp()
const agentId = Number(useRoute().params.agentId)
const agent = computed(() => {
  const application = $store.getters['application/get'](agentId)
  return application?.type === AGENT_APPLICATION_TYPE ? application : null
})
useHead(() => ({ title: agent.value?.name }))

await usePageAsyncData(`agent-${agentId}`, async () => {
  try {
    // Applications are already loaded by middleware. Record this visit without
    // fetching the same public data again.
    await AgentApplicationService($client).recordView(agentId)
    return true
  } catch (error) {
    if (!error.response) {
      throw error
    }
    const statusCode = error.response.status
    throw createError({
      statusCode,
      message:
        statusCode === 404 ? 'Agent not found.' : normalizeError(error).message,
      data: { report: statusCode >= 500 },
      fatal: true,
    })
  }
})
</script>
