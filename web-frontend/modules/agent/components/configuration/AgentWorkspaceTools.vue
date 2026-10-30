<template>
  <div class="agent-workspace-tools">
    <div class="agent-workspace-tools__head">
      <div>
        <div class="agent-workspace-tools__title">
          {{ $t('agent.workspaceTools') }}
        </div>
        <div class="agent-workspace-tools__description">
          {{ $t('agent.workspaceToolsDescription') }}
        </div>
      </div>
      <SwitchInput
        small
        :model-value="allowedTools.length > 0"
        :disabled="!editable"
        @update:model-value="emit('update', $event ? readTools : [])"
      />
    </div>
    <template v-if="allowedTools.length">
      <SegmentControl
        class="agent-workspace-tools__presets"
        :segments="presets"
        :active-index="presetIndex"
        size="small"
        @update:active-index="choosePreset"
      />
      <a
        v-for="group in groups"
        :key="group.type"
        class="agent-workspace-tools__group"
        :class="{ 'agent-workspace-tools__group--disabled': !editable }"
        @click="editable && permissions.show()"
      >
        <i :class="group.icon"></i>
        <span class="agent-workspace-tools__group-name">{{ group.label }}</span>
        <span class="agent-workspace-tools__group-count">
          {{
            $t('agent.toolsOn', {
              count: group.tools.filter((tool) =>
                allowedTools.includes(tool.name)
              ).length,
              total: group.tools.length,
            })
          }}
        </span>
        <i class="iconoir-nav-arrow-right"></i>
      </a>
    </template>
    <AgentToolPermissionsModal
      ref="permissions"
      :available-tools="availableTools"
      :allowed-tools="allowedTools"
      :agent-name="agentName"
      @save="emit('update', $event)"
    />
  </div>
</template>

<script setup>
import { useNuxtApp } from '#app'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'
import { groupAgentTools } from '@baserow/modules/agent/agentTools'
import AgentToolPermissionsModal from '@baserow/modules/agent/components/configuration/AgentToolPermissionsModal'

/**
 * Turns an Agent's workspace tools on and off with presets, or one by one in the
 * tool permissions modal. Emits `update` with the names of the tools to allow.
 */
const props = defineProps({
  allowedTools: { type: Array, required: true },
  availableTools: { type: Array, required: true },
  agentName: { type: String, required: true },
  editable: Boolean,
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

function choosePreset(index) {
  if (!props.editable) return
  if (index === 0) emit('update', allTools.value)
  else if (index === 1) emit('update', readTools.value)
  else permissions.value.show()
}
</script>
