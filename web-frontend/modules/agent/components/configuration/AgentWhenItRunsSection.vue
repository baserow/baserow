<template>
  <section class="agent-triggers" :aria-busy="loading">
    <div class="agent-triggers__header">
      <h3 class="agent-triggers__title">{{ $t('agent.triggers') }}</h3>
      <ButtonText
        v-if="editable && availableTypes.length"
        type="primary"
        size="small"
        button-type="button"
        icon="iconoir-plus"
        class="agent-triggers__add"
        aria-haspopup="menu"
        @click="picker.toggle($event.currentTarget)"
      >
        {{ $t('agent.addTrigger') }}
      </ButtonText>
    </div>
    <div v-if="loading" class="skeleton" aria-hidden="true">
      <SkeletonBlock width="100%" height="120px" />
    </div>
    <Alert v-else-if="loadError" type="error">
      {{ $t('agent.triggersLoadError') }}
      <template #actions
        ><Button
          type="secondary"
          size="small"
          button-type="button"
          @click="fetchTriggers"
          >{{ $t('action.retry') }}</Button
        ></template
      >
    </Alert>
    <p v-else-if="!triggers.length" class="agent-triggers__empty">
      {{ $t('agent.noTriggers') }}
    </p>
    <div v-else class="agent-triggers__list">
      <AgentTriggerCard
        v-for="trigger in triggers"
        :key="trigger.id"
        :trigger="trigger"
        :workspace="workspace"
        :editable="editable"
        :saving="savingIds.has(trigger.id)"
        :service-error="serviceErrors[trigger.id] || ''"
        @update="updateTrigger(trigger, $event)"
        @delete="deleteTrigger(trigger)"
      />
    </div>
    <AgentTriggerPicker
      ref="picker"
      :available-types="availableTypes"
      :workspace="workspace"
      @select="createTrigger"
    />
  </section>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import { useStore } from 'vuex'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import AgentTriggerCard from '@baserow/modules/agent/components/configuration/AgentTriggerCard'
import AgentTriggerPicker from '@baserow/modules/agent/components/configuration/AgentTriggerPicker'
import { useAgentTriggers } from '@baserow/modules/agent/composables/useAgentTriggers'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  /** The Agent's configuration, with its available trigger types. */
  configuration: { type: Object, required: true },
  /** Whether the user may add, change and delete triggers. */
  editable: Boolean,
})
const store = useStore()
const agent = inject('agentApplication')
const picker = ref(null)
const workspace = computed(() =>
  agent.value ? store.getters['workspace/get'](agent.value.workspace.id) : null
)
const availableTypes = computed(
  () => props.configuration.available_trigger_types || []
)
const {
  triggers,
  loading,
  loadError,
  savingIds,
  serviceErrors,
  fetchTriggers,
  createTrigger,
  updateTrigger,
  deleteTrigger,
} = useAgentTriggers(agent)
</script>
