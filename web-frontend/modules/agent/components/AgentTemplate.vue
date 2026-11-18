<template>
  <div class="agent-template">
    <div class="agent-template__content">
      <h1 class="agent-template__title">{{ agent.name }}</h1>
      <p class="agent-template__hint">{{ $t('agent.templatePreviewHint') }}</p>
      <div v-if="loading" class="loading"></div>
      <Alert v-else-if="loadError" type="error">
        {{ $t('agent.templatePreviewLoadError') }}
      </Alert>
      <template v-else>
        <section class="agent-template__section">
          <h2 class="agent-template__heading">
            {{ $t('agent.instructions') }}
          </h2>
          <p class="agent-template__instructions">
            {{ configuration.instructions }}
          </p>
        </section>
        <section class="agent-template__section">
          <h2 class="agent-template__heading">{{ $t('agent.model') }}</h2>
          <p class="agent-template__text">{{ model }}</p>
        </section>
        <section class="agent-template__section">
          <h2 class="agent-template__heading">
            {{ $t('agent.workspaceTools') }}
          </h2>
          <ul v-if="tools.length" class="agent-template__list">
            <li v-for="tool in tools" :key="tool.name">{{ tool.label }}</li>
          </ul>
          <p v-else class="agent-template__empty">
            {{ $t('agent.templatePreviewNoTools') }}
          </p>
        </section>
        <section v-if="servers.length" class="agent-template__section">
          <h2 class="agent-template__heading">
            {{ $t('agent.connectedApps') }}
          </h2>
          <ul class="agent-template__list">
            <li v-for="server in servers" :key="server.id">
              {{ server.name }}
            </li>
          </ul>
        </section>
        <section class="agent-template__section">
          <h2 class="agent-template__heading">{{ $t('agent.whenItRuns') }}</h2>
          <ul v-if="triggers.length" class="agent-template__list">
            <li v-for="trigger in triggers" :key="trigger.id">
              {{ triggerName(trigger) }}
            </li>
          </ul>
          <p v-else class="agent-template__empty">
            {{ $t('agent.templatePreviewNoTriggers') }}
          </p>
        </section>
        <section v-if="actions.length" class="agent-template__section">
          <h2 class="agent-template__heading">{{ $t('agent.actions') }}</h2>
          <ul class="agent-template__list">
            <li v-for="action in actions" :key="action.id">
              {{ actionName(action) }}
            </li>
          </ul>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import AgentTriggerService from '@baserow/modules/agent/services/agentTriggers'
import AgentActionService from '@baserow/modules/agent/services/agentActions'
import IntegrationService from '@baserow/modules/core/services/integration'
import { agentToolLabel } from '@baserow/modules/agent/agentTools'
import { serviceTypeOf } from '@baserow/modules/agent/utils/triggers'

/**
 * Shows an Agent of a template read-only. It only reads what a template preview
 * may read, so nothing here needs the visitor to be a workspace member.
 */
const props = defineProps({
  pageValue: { type: Object, required: true },
})
const { $client, $registry } = useNuxtApp()
const { t } = useI18n()
const agent = computed(() => props.pageValue.agent)
const loading = ref(true)
const loadError = ref(false)
const configuration = ref({})
const triggers = ref([])
const actions = ref([])
const servers = ref([])
let request = 0

const model = computed(() =>
  [configuration.value.provider_type, configuration.value.model_identifier]
    .filter(Boolean)
    .join(' · ')
)
// An installed template's agent turns on the pending tools with an identity.
const tools = computed(() => {
  const names = configuration.value.run_as
    ? configuration.value.allowed_tools
    : configuration.value.pending_tools
  return (names || []).map((name) => ({
    name,
    label: agentToolLabel(name, $registry, t),
  }))
})

function triggerName(trigger) {
  const serviceType = serviceTypeOf($registry, trigger.type)
  return (
    trigger.name ||
    serviceType?.getDefaultName(trigger.service, {}) ||
    serviceType?.name ||
    trigger.type
  )
}

function actionName(action) {
  return (
    action.name || serviceTypeOf($registry, action.type)?.name || action.type
  )
}

async function load(agentId) {
  const current = ++request
  loading.value = true
  loadError.value = false
  try {
    const [
      configurationResponse,
      triggersResponse,
      actionsResponse,
      integrationsResponse,
    ] = await Promise.all([
      AgentApplicationService($client).getConfiguration(agentId),
      AgentTriggerService($client).list(agentId),
      AgentActionService($client).list(agentId),
      IntegrationService($client).fetchAll(agentId),
    ])
    if (current !== request) return
    configuration.value = configurationResponse.data
    triggers.value = triggersResponse.data
    actions.value = actionsResponse.data
    servers.value = integrationsResponse.data
  } catch {
    if (current === request) loadError.value = true
  } finally {
    if (current === request) loading.value = false
  }
}

watch(() => agent.value.id, load, { immediate: true })
</script>
