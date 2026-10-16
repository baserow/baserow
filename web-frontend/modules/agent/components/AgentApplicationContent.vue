<template>
  <div class="agent-application">
    <header class="layout__col-2-1 header agent-application__header">
      <div class="agent-application__header-name">{{ agent.name }}</div>
      <ButtonIcon
        v-if="state.canReadSettings"
        icon="iconoir-settings"
        :active="configurationOpen"
        class="agent-application__configuration-toggle"
        :aria-label="$t('agent.configuration')"
        :title="$t('agent.configuration')"
        :aria-expanded="configurationOpen"
        @click="configurationOpen = !configurationOpen"
      />
    </header>
    <div class="layout__col-2-2 agent-application__content">
      <main class="agent-chat">
        <div class="agent-chat__history">
          <div class="agent-chat__intro">
            <div class="agent-chat__avatar">
              <img :src="agentOrb" alt="" />
            </div>
            <i18n-t scope="global" keypath="agent.talkTo" tag="h1">
              <template #name>
                <span class="agent-chat__intro-name">{{ agent.name }}</span>
              </template>
            </i18n-t>
            <p>{{ $t('agent.chatDescription') }}</p>
          </div>
        </div>
        <div class="agent-chat__footer">
          <Alert
            v-if="showConfigurationWarning"
            type="warning"
            class="agent-chat__warning"
          >
            <template #title>{{ $t(warningTitle) }}</template>
            <p>{{ $t(warningMessage) }}</p>
            <template #actions>
              <template
                v-if="
                  state.canReadSettings &&
                  state.canUpdateSettings &&
                  warningFields.length
                "
              >
                <button
                  v-for="field in warningFields"
                  :key="field"
                  class="agent-chat__warning-link"
                  @click="focusConfiguration(field)"
                >
                  {{ $t(fieldLabels[field]) }}
                </button>
              </template>
              <Button
                v-else-if="hasLoadError"
                type="secondary"
                size="small"
                @click="state.refreshConfiguration"
                >{{ $t('action.retry') }}</Button
              >
              <Button
                v-else-if="state.canUpdateSettings && state.settingsSaveError"
                type="secondary"
                size="small"
                @click="state.saveSettings"
                >{{ $t('action.retry') }}</Button
              >
            </template>
          </Alert>
        </div>
      </main>
      <AgentConfigurationSidebar
        v-if="state.canReadSettings && configurationOpen"
        ref="configurationSidebar"
        :configuration="state.configuration"
        :errors="state.fieldErrors"
        :enabled-models="state.enabledModels"
        :editable="state.canUpdateSettings"
        :loading="state.configurationLoading"
        :load-error="state.configurationLoadError"
        :availability-loading="state.availabilityLoading"
        :saving="state.savingSettings"
        :save-error="state.settingsSaveError"
        @close="configurationOpen = false"
        @change="state.updateConfiguration"
        @flush="state.saveSettings"
        @reload="state.refreshConfiguration"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, toRef } from 'vue'
import agentOrb from '@baserow/modules/agent/assets/images/agent-orb.svg?url'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'
import { useAgentConfiguration } from '@baserow/modules/agent/composables/useAgentConfiguration'

const props = defineProps({ agent: { type: Object, required: true } })
const state = reactive(useAgentConfiguration(toRef(props, 'agent')))
const configurationOpen = ref(true)
const configurationSidebar = ref(null)
const fieldLabels = {
  name: 'agent.name',
  instructions: 'agent.instructions',
  provider_type: 'agent.provider',
  model_identifier: 'agent.model',
}
const warningFields = computed(() => Object.keys(state.fieldErrors))
const hasLoadError = computed(
  () =>
    state.readinessError ||
    state.availabilityError ||
    (state.canReadSettings && state.configurationLoadError)
)
const showConfigurationWarning = computed(() =>
  Boolean(
    hasLoadError.value ||
    (state.canReadSettings &&
      (state.settingsSaveError ||
        (!state.configurationLoading && warningFields.value.length))) ||
    ['incomplete', 'unavailable'].includes(state.readiness)
  )
)
const warningTitle = computed(() =>
  hasLoadError.value
    ? 'agent.readinessLoadError'
    : state.settingsSaveError
      ? 'agent.configurationSaveError'
      : 'agent.configurationRequired'
)
const warningMessage = computed(() =>
  hasLoadError.value
    ? 'agent.readinessRetry'
    : state.canReadSettings && state.canUpdateSettings
      ? state.readiness === 'unavailable' ||
        state.fieldErrors.model_identifier === 'unavailable'
        ? 'agent.modelUnavailable'
        : 'agent.completeConfiguration'
      : 'agent.configurationPermissionRequired'
)
async function focusConfiguration(field) {
  configurationOpen.value = true
  await nextTick()
  await configurationSidebar.value?.focusField(field)
}
</script>
