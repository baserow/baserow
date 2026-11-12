<template>
  <section class="agent-actions" :aria-busy="loading">
    <div class="agent-actions__header">
      <h3>{{ $t('agent.actions') }}</h3>
      <ButtonText
        v-if="editable && availableTypes.length"
        type="primary"
        size="small"
        button-type="button"
        icon="iconoir-plus"
        :disabled="loading"
        aria-haspopup="menu"
        @click="picker.toggle($event.currentTarget)"
        >{{ $t('agent.addAction') }}</ButtonText
      >
    </div>
    <ButtonText
      v-if="actions.length"
      class="agent-card-list__toggle-all"
      type="secondary"
      size="small"
      button-type="button"
      @click="toggleAll"
    >
      {{ $t(allExpanded ? 'agent.collapseAll' : 'agent.expandAll') }}
    </ButtonText>
    <div v-if="loading && !actions.length" class="skeleton" aria-hidden="true">
      <SkeletonBlock width="100%" height="120px" />
    </div>
    <Alert v-else-if="loadError" type="error">
      {{ $t('agent.actionsLoadError') }}
      <template #actions
        ><Button
          type="secondary"
          size="small"
          button-type="button"
          @click="fetchActions({ integrations: true })"
          >{{ $t('action.retry') }}</Button
        ></template
      >
    </Alert>
    <p v-else-if="!actions.length" class="agent-actions__empty">
      {{ $t('agent.noActions') }}
    </p>
    <div v-else class="agent-actions__list">
      <AgentActionCard
        v-for="action in actions"
        :key="action.id"
        :expanded="expandedIds.has(action.id)"
        :action="action"
        :workspace="workspace"
        :editable="editable"
        :saving="savingIds.has(action.id)"
        :save-error="saveErrors[action.id] || ''"
        @toggle="toggle(action.id)"
        @update="updateAction(action, $event)"
        @delete="deleteAction(action)"
        @retry="flush(action)"
      />
    </div>
    <AgentServicePicker
      ref="picker"
      :available-types="availableTypes"
      :workspace="workspace"
      :search-placeholder="$t('agent.searchActionTypes')"
      :empty-text="$t('agent.noActionTypes')"
      @select="addAction"
    />
  </section>
</template>

<script setup>
import { computed, inject, ref, watch } from 'vue'
import { useExpandedItems } from '@baserow/modules/agent/composables/useExpandedItems'
import { useStore } from 'vuex'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import AgentActionCard from '@baserow/modules/agent/components/configuration/AgentActionCard'
import AgentServicePicker from '@baserow/modules/agent/components/configuration/AgentServicePicker'
import { useAgentActions } from '@baserow/modules/agent/composables/useAgentActions'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  configuration: { type: Object, required: true },
  editable: Boolean,
})
const store = useStore()
const agent = inject('agentApplication')
const picker = ref(null)
const workspace = computed(() =>
  agent.value ? store.getters['workspace/get'](agent.value.workspace.id) : null
)
const availableTypes = computed(
  () => props.configuration.available_action_types || []
)
const {
  actions,
  loading,
  loadError,
  savingIds,
  saveErrors,
  fetchActions,
  createAction,
  updateAction,
  deleteAction,
  flush,
} = useAgentActions(agent)
const { expandedIds, allExpanded, toggle, toggleAll } =
  useExpandedItems(actions)
watch(
  () => agent.value?.id,
  () => expandedIds.clear()
)
async function addAction(type) {
  const item = await createAction(type)
  if (item) expandedIds.add(item.id)
}
</script>
