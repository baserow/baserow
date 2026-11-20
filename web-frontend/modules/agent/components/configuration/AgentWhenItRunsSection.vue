<template>
  <section class="agent-triggers" :aria-busy="loading">
    <div class="agent-triggers__header">
      <h3 class="agent-triggers__title">{{ $t('agent.triggers') }}</h3>
      <ButtonText
        v-if="canAddTriggers"
        type="primary"
        size="small"
        button-type="button"
        icon="iconoir-plus"
        class="agent-triggers__add"
        :disabled="creating"
        :loading="creating"
        aria-haspopup="menu"
        @click="picker.toggle($event.currentTarget)"
      >
        {{ $t('agent.addTrigger') }}
      </ButtonText>
    </div>
    <Alert v-if="typesLoadError && !loading && !loadError" type="error">
      {{ $t('agent.triggerTypesLoadError') }}
      <template #actions
        ><Button
          type="secondary"
          size="small"
          button-type="button"
          @click="retryLoad"
          >{{ $t('action.retry') }}</Button
        ></template
      >
    </Alert>
    <AgentCardListHeader
      v-if="!loading && !loadError && triggers.length"
      :all-expanded="allExpanded"
      @toggle-all="toggleAll"
    />
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
          @click="retryLoad"
          >{{ $t('action.retry') }}</Button
        ></template
      >
    </Alert>
    <p v-else-if="!triggers.length" class="agent-triggers__empty">
      {{ $t('agent.noTriggers') }}
    </p>
    <div v-else ref="list" class="agent-triggers__list">
      <AgentTriggerCard
        v-for="trigger in triggers"
        :key="trigger.id"
        :data-card-id="trigger.id"
        :expanded="expandedIds.has(trigger.id)"
        :trigger="trigger"
        :workspace="workspace"
        :editable="editable"
        :max-queued-trigger-runs="configuration.max_queued_trigger_runs"
        :max-parallel-trigger-runs="configuration.max_parallel_trigger_runs"
        :type-options="typeOptionsOf(trigger)"
        :types-version="typesVersion"
        :run-as-active="runAsActive"
        :available-types="availableTypes"
        :saving="savingIds.has(trigger.id)"
        :service-error="serviceErrors[trigger.id] || ''"
        :service-reverts="serviceReverts[trigger.id] || 0"
        @toggle="toggle(trigger.id)"
        @update="updateTrigger(trigger, $event)"
        @change-type="changeTriggerType(trigger, $event)"
        @delete="deleteTrigger(trigger)"
      />
    </div>
    <AgentTriggerPicker
      ref="picker"
      :available-types="availableTypes"
      :workspace="workspace"
      @select="addItem"
    />
  </section>
</template>

<script setup>
import { computed, inject, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { useAgentCardList } from '@baserow/modules/agent/composables/useExpandedItems'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import AgentCardListHeader from '@baserow/modules/agent/components/configuration/AgentCardListHeader'
import AgentTriggerCard from '@baserow/modules/agent/components/configuration/AgentTriggerCard'
import AgentTriggerPicker from '@baserow/modules/agent/components/configuration/AgentTriggerPicker'
import { useAgentTriggers } from '@baserow/modules/agent/composables/useAgentTriggers'
import { RUN_AS_STATUS } from '@baserow/modules/agent/constants'
import { getRunAsStatus } from '@baserow/modules/agent/utils/runAs'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  /** The Agent's configuration: trigger types, queued run cap and run identity. */
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
const runAsActive = computed(
  () => getRunAsStatus(props.configuration.run_as) === RUN_AS_STATUS.ACTIVE
)
const {
  triggers,
  allTriggers,
  triggerTypes,
  typesVersion,
  loading,
  loadError,
  typesLoadError,
  savingIds,
  serviceErrors,
  serviceReverts,
  retryLoad,
  createTrigger,
  updateTrigger,
  changeTriggerType,
  deleteTrigger,
} = useAgentTriggers(agent, () => props.configuration.run_as)
const { expandedIds, allExpanded, toggle, toggleAll, list, creating, addItem } =
  useAgentCardList(triggers, createTrigger, allTriggers)
watch(
  () => agent.value?.id,
  () => expandedIds.clear()
)
// Initialize once per successful opening, preserving later manual toggles.
let initializedFor = null
watch([loading, () => agent.value?.id], ([busy, id]) => {
  if (busy || loadError.value || !id || initializedFor === id) return
  initializedFor = id
  if (triggers.value.length === 1) expandedIds.add(triggers.value[0].id)
})
// A trigger added before the list loaded would be dropped by the list reply.
const canAddTriggers = computed(
  () =>
    props.editable &&
    availableTypes.value.length > 0 &&
    !loading.value &&
    !loadError.value
)

/**
 * @param {object} trigger A trigger of the list.
 * @returns {object|null} What the run identity offers its type, empty for a
 *   type the Agent no longer offers, or null while the types load.
 */
const typeOptionsOf = (trigger) =>
  triggerTypes.value && (triggerTypes.value[trigger.type] || {})
</script>
