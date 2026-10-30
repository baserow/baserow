<template>
  <FormGroup
    :label="$t('agent.runAs')"
    :error="trashed"
    :error-message="
      trashed
        ? $t('agent.runAsTrashed', { name: configuration.run_as.name })
        : ''
    "
    small-label
    required
  >
    <PaginatedDropdown
      ref="runAsDropdown"
      :value="selected"
      :fetch-page="fetchIdentities"
      :add-empty-item="false"
      :initial-display-name="initialName"
      :include-display-name-in-selected-event="true"
      :disabled="!editable"
      @input="select"
    >
      <template #items="{ results }">
        <DropdownItem
          :name="$t('agent.noWorkspaceAccess')"
          :value="NO_WORKSPACE_ACCESS"
          icon="iconoir-prohibition"
        />
        <DropdownItem
          v-for="subject in results"
          :key="subject.id"
          :name="subject.name"
          :value="subject.id"
          icon="baserow-icon-agent"
        />
      </template>
    </PaginatedDropdown>
    <template #helper>
      {{
        configuration.run_as
          ? $t('agent.runAsHelper', { name: configuration.run_as.name })
          : $t('agent.noWorkspaceAccessHelper')
      }}
    </template>
  </FormGroup>
  <AgentWorkspaceTools
    class="margin-top-3"
    :allowed-tools="configuration.allowed_tools"
    :available-tools="configuration.available_tools"
    :agent-name="agent.name"
    :editable="editable"
    @update="changeAllowedTools"
  />
</template>

<script setup>
import { computed, inject, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import SubjectService from '@baserow/modules/core/services/subject'
import AgentWorkspaceTools from '@baserow/modules/agent/components/configuration/AgentWorkspaceTools'

const NO_WORKSPACE_ACCESS = 'none'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  configuration: { type: Object, required: true },
  editable: Boolean,
})
const emit = defineEmits(['change', 'flush'])
const { $client } = useNuxtApp()
const { t } = useI18n()
const agent = inject('agentApplication')
const runAsDropdown = ref(null)

const trashed = computed(() => Boolean(props.configuration.run_as?.trashed))
const selected = computed(() => {
  const runAs = props.configuration.run_as
  return runAs ? `${runAs.type}:${runAs.id}` : NO_WORKSPACE_ACCESS
})
const initialName = computed(
  () => props.configuration.run_as?.name ?? t('agent.noWorkspaceAccess')
)

// Refresh the cached label after the dropdown receives its updated prop.
watch(initialName, () => runAsDropdown.value?.clear(), { flush: 'post' })

function fetchIdentities(page, search) {
  return SubjectService($client).list(agent.value.workspace.id, {
    page,
    search,
    subjectTypes: 'core.Agent',
  })
}

function changeAllowedTools(allowedTools) {
  emit('change', { allowed_tools: allowedTools })
  emit('flush')
}

function select({ value, item }) {
  if (value === selected.value) return
  emit('change', {
    run_as:
      value === NO_WORKSPACE_ACCESS
        ? null
        : {
            type: item.subject_type,
            id: item.subject_id,
            name: item.name,
            trashed: false,
          },
  })
  emit('flush')
}
</script>
