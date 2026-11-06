<template>
  <div class="agent-workspace-tools">
    <div class="agent-workspace-tools__head">
      <div>
        <div class="agent-workspace-tools__title">
          {{ $t('agent.workspaceTools') }}
        </div>
        <div class="agent-workspace-tools__description">
          {{ disabledReason || $t('agent.workspaceToolsDescription') }}
        </div>
      </div>
      <SwitchInput
        class="agent-workspace-tools__switch"
        small
        role="switch"
        :tabindex="editable ? 0 : -1"
        :aria-label="$t('agent.workspaceTools')"
        :aria-checked="allowedTools.length > 0"
        :aria-disabled="!editable"
        :model-value="allowedTools.length > 0"
        :disabled="!editable"
        @update:model-value="setEnabled"
        @keydown.enter.prevent="setEnabled(!allowedTools.length)"
        @keydown.space.prevent="setEnabled(!allowedTools.length)"
      />
    </div>
    <template v-if="allowedTools.length">
      <SegmentControl
        class="agent-workspace-tools__presets"
        :segments="presets"
        :active-index="presetIndex"
        :disabled="!editable"
        size="small"
        @update:active-index="choosePreset"
      />
      <div class="agent-workspace-tools__ask">
        <div class="agent-workspace-tools__ask-text">
          <div class="agent-workspace-tools__ask-title">
            {{ $t('agent.askBeforeChanges') }}
          </div>
          <div class="agent-workspace-tools__ask-description">
            {{ $t('agent.askBeforeChangesDescription') }}
          </div>
        </div>
        <SwitchInput
          class="agent-workspace-tools__switch"
          small
          role="checkbox"
          :tabindex="canAskBeforeChanges ? 0 : -1"
          :aria-label="$t('agent.askBeforeChanges')"
          :aria-checked="askBeforeChanges ?? 'mixed'"
          :aria-disabled="!canAskBeforeChanges"
          :model-value="askBeforeChanges"
          :disabled="!canAskBeforeChanges"
          @update:model-value="setAskBeforeChanges"
          @keydown.enter.prevent="toggleAskBeforeChanges"
          @keydown.space.prevent="toggleAskBeforeChanges"
        />
      </div>
      <button
        v-for="group in groups"
        :key="group.type"
        type="button"
        class="agent-workspace-tools__group"
        :class="{ 'agent-workspace-tools__group--disabled': !editable }"
        :disabled="!editable"
        aria-haspopup="dialog"
        @click="permissions.show()"
      >
        <i :class="group.icon"></i>
        <span class="agent-workspace-tools__group-name">{{ group.label }}</span>
        <span class="agent-workspace-tools__group-count">
          {{
            $t(disabledReason ? 'agent.toolsSelected' : 'agent.toolsSummary', {
              on: countIn(group, allowedTools),
              total: group.tools.length,
            })
          }}
          <template v-if="countIn(group, askFirstTools)">
            <span class="agent-workspace-tools__group-separator">•</span>
            {{
              $t('agent.toolsAskCount', {
                count: countIn(group, askFirstTools),
              })
            }}
          </template>
        </span>
        <i class="iconoir-nav-arrow-right"></i>
      </button>
    </template>
    <AgentToolPermissionsModal
      ref="permissions"
      :available-tools="availableTools"
      :allowed-tools="allowedTools"
      :ask-first-tools="askFirstTools"
      :agent-name="agentName"
      :editable="editable"
      @save="emit('update', $event)"
    />
  </div>
</template>

<script setup>
import { useNuxtApp } from '#app'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'
import {
  groupAgentTools,
  nextAskFirst,
} from '@baserow/modules/agent/agentTools'
import AgentToolPermissionsModal from '@baserow/modules/agent/components/configuration/AgentToolPermissionsModal'

/** Tool presets, permissions and the ask-before-changes switch. */
const props = defineProps({
  allowedTools: { type: Array, required: true },
  askFirstTools: { type: Array, required: true },
  availableTools: { type: Array, required: true },
  agentName: { type: String, required: true },
  editable: Boolean,
  disabledReason: { type: String, default: '' },
})
const emit = defineEmits(['update'])
const { t } = useI18n()
const { $registry } = useNuxtApp()

const permissions = ref(null)
const groups = computed(() =>
  groupAgentTools(props.availableTools, $registry, t)
)
const allTools = computed(() => props.availableTools.map((tool) => tool.name))
const readTools = computed(() =>
  props.availableTools
    .filter((tool) => !tool.changes_data)
    .map((tool) => tool.name)
)
const allowedChangeTools = computed(() =>
  props.availableTools
    .filter(
      (tool) => tool.changes_data && props.allowedTools.includes(tool.name)
    )
    .map((tool) => tool.name)
)
const canAskBeforeChanges = computed(
  () => props.editable && allowedChangeTools.value.length > 0
)
/** True if every allowed change tool asks first, false if none, else null. */
const askBeforeChanges = computed(() => {
  const asking = allowedChangeTools.value.filter((name) =>
    props.askFirstTools.includes(name)
  ).length
  if (!asking) return false
  return asking === allowedChangeTools.value.length ? true : null
})
const presets = computed(() => [
  { label: t('agent.toolsEverything') },
  { label: t('agent.toolsReadOnly') },
  { label: t('agent.toolsCustom') },
])

const isExactly = (names) =>
  names.length === props.allowedTools.length &&
  names.every((name) => props.allowedTools.includes(name))
const presetIndex = computed(() => {
  if (isExactly(allTools.value)) return 0
  if (isExactly(readTools.value)) return 1
  return 2
})
const countIn = (group, names) =>
  group.tools.filter((tool) => names.includes(tool.name)).length

function allow(names) {
  emit('update', {
    allowed_tools: names,
    ask_first_tools: nextAskFirst(
      props.availableTools,
      props.allowedTools,
      props.askFirstTools,
      names
    ),
  })
}

function choosePreset(index) {
  if (!props.editable) return
  if (index === 0) allow(allTools.value)
  else if (index === 1) allow(readTools.value)
  else permissions.value.show()
}

function setEnabled(enabled) {
  if (!props.editable) return
  allow(enabled ? readTools.value : [])
}

function setAskBeforeChanges(ask) {
  if (!canAskBeforeChanges.value) return
  const changeTools = new Set(allowedChangeTools.value)
  emit('update', {
    ask_first_tools: props.availableTools
      .filter((tool) =>
        changeTools.has(tool.name)
          ? ask
          : props.askFirstTools.includes(tool.name)
      )
      .map((tool) => tool.name),
  })
}

function toggleAskBeforeChanges() {
  setAskBeforeChanges(askBeforeChanges.value !== true)
}
</script>
