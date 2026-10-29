<template>
  <FormGroup
    :label="$t('agent.runAs')"
    :error="unavailable"
    :error-message="errorMessage"
    :helper-text="helperText"
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
      :error="unavailable"
      :refresh-key="optionsVersion"
      fetch-on-open
      refresh-on-open
      fixed-items
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
  </FormGroup>
  <AgentWorkspaceTools
    class="margin-top-3"
    :tools="configuration.tools"
    :available-tools="configuration.available_tools"
    :agent-name="agent.name"
    :editable="editable"
    @update="changeTools"
  />
</template>

<script setup>
import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import debounce from 'lodash/debounce'
import { useI18n } from 'vue-i18n'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import { getRunAsStatus } from '@baserow/modules/agent/utils/runAs'
import { RUN_AS_STATUS } from '@baserow/modules/agent/constants'
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

const status = computed(() => getRunAsStatus(props.configuration.run_as))
const unavailable = computed(() =>
  [RUN_AS_STATUS.TRASHED, RUN_AS_STATUS.MISSING].includes(status.value)
)
const errorMessage = computed(() => {
  if (status.value === RUN_AS_STATUS.TRASHED)
    return t('agent.runAsTrashed', { name: props.configuration.run_as.name })
  return status.value === RUN_AS_STATUS.MISSING ? t('agent.runAsMissing') : ''
})
const helperText = computed(() => {
  if (unavailable.value) return ''
  return props.configuration.run_as
    ? t('agent.runAsHelper', { name: props.configuration.run_as.name })
    : t('agent.noWorkspaceAccessHelper')
})
const selected = computed(() => {
  const runAs = props.configuration.run_as
  return runAs ? `${runAs.type}:${runAs.id}` : NO_WORKSPACE_ACCESS
})
const initialName = computed(
  () =>
    props.configuration.run_as?.name ??
    t(
      status.value === RUN_AS_STATUS.MISSING
        ? 'agent.runAsMissingLabel'
        : 'agent.noWorkspaceAccess'
    )
)

const optionsVersion = ref(0)
const refreshOptions = debounce(() => ++optionsVersion.value, 100, {
  maxWait: 500,
})
watch(() => agent.value?._?.runAsOptionsVersion, refreshOptions)
onBeforeUnmount(() => refreshOptions.cancel())

// Refresh the cached label after the dropdown receives its updated prop.
watch(initialName, () => runAsDropdown.value?.clear(), { flush: 'post' })

function fetchIdentities(page, search) {
  return AgentApplicationService($client).getRunAsSubjects(
    agent.value.id,
    page,
    search
  )
}

function changeTools(tools) {
  emit('change', { tools })
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
            status: RUN_AS_STATUS.ACTIVE,
          },
  })
  emit('flush')
}
</script>
