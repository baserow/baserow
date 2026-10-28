<template>
  <div class="mcp-tool-picker">
    <div class="mcp-tool-picker__head">
      <span class="mcp-tool-picker__label">{{
        $t('mcpToolPicker.tools')
      }}</span>
      <span class="mcp-tool-picker__presets">
        <button
          type="button"
          class="mcp-tool-picker__preset"
          data-test="mcp-tool-picker-read-only"
          @click="select(readOnlyNames)"
        >
          {{ $t('mcpToolPicker.readOnly') }}
        </button>
        <span aria-hidden="true"> · </span>
        <button
          type="button"
          class="mcp-tool-picker__preset"
          data-test="mcp-tool-picker-full-access"
          @click="select(availableNames)"
        >
          {{ $t('mcpToolPicker.fullAccess') }}
        </button>
        <span aria-hidden="true"> · </span>
        <button
          type="button"
          class="mcp-tool-picker__preset"
          data-test="mcp-tool-picker-none"
          @click="select([])"
        >
          {{ $t('mcpToolPicker.none') }}
        </button>
      </span>
    </div>
    <p v-if="!areas.length" class="mcp-tool-picker__empty">
      {{ $t('mcpToolPicker.noTools') }}
    </p>
    <div v-else class="mcp-tool-picker__list">
      <div
        v-for="area in areas"
        :key="area.key"
        class="mcp-tool-picker__area"
        :data-test="`mcp-tool-picker-area-${area.key}`"
      >
        <div class="mcp-tool-picker__area-title">{{ area.label }}</div>
        <div
          v-for="group in area.groups"
          :key="group.type"
          class="mcp-tool-picker__group"
          :data-test="`mcp-tool-picker-group-${group.type}`"
        >
          <div class="mcp-tool-picker__group-title">
            <Checkbox
              :model-value="groupState(group) === 'all'"
              :indeterminate="groupState(group) === 'some'"
              :data-test="`mcp-tool-picker-group-toggle-${group.type}`"
              @update:model-value="toggleGroup(group, $event)"
            >
              {{ group.label }}
            </Checkbox>
          </div>
          <div
            v-for="tool in group.tools"
            :key="tool.name"
            class="mcp-tool-picker__tool"
          >
            <Checkbox
              :model-value="selected.has(tool.name)"
              class="mcp-tool-picker__tool-checkbox"
              :data-test="`mcp-tool-picker-tool-${tool.name}`"
              @update:model-value="toggle([tool.name], $event)"
            >
              {{ tool.title }}
            </Checkbox>
            <Badge
              v-if="tool.destructive"
              :color="isDelete(tool) ? 'red' : 'yellow'"
              size="small"
              class="mcp-tool-picker__badge"
              :data-test="`mcp-tool-picker-badge-${tool.name}`"
              >{{
                isDelete(tool)
                  ? $t('mcpToolPicker.deletes')
                  : $t('mcpToolPicker.overwrites')
              }}</Badge
            >
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  listedTools,
  readOnlyToolNames,
} from '@baserow/modules/core/utils/mcpTools'

const props = defineProps({
  /**
   * The tools as the API lists them: `name`, `title`, `read_only`,
   * `destructive` and `group`.
   */
  tools: { type: Array, required: true },
  /**
   * The tool groups in display order: `type`, `title`, `area` and
   * `read_only_preset`.
   */
  groups: { type: Array, required: true },
  /**
   * The picked tool names.
   */
  modelValue: { type: Array, required: true },
})

const emit = defineEmits(['update:modelValue'])

const { t } = useI18n()

// Translations of the groups and areas the frontend knows. Others fall back to
// the API's English title.
const GROUP_LABELS = {
  database_read: 'mcpToolPicker.databaseRead',
  database_edit: 'mcpToolPicker.databaseEdit',
  database_delete: 'mcpToolPicker.databaseDelete',
  automation_read: 'mcpToolPicker.automationRead',
  automation_edit: 'mcpToolPicker.automationEdit',
  automation_delete: 'mcpToolPicker.automationDelete',
}
const AREA_LABELS = {
  database: 'mcpToolPicker.areaDatabase',
  automation: 'mcpToolPicker.areaAutomation',
}

// The tools the user sees: a tool is only listed under one of the groups.
const availableTools = computed(() => listedTools(props.tools, props.groups))

const availableNames = computed(() =>
  availableTools.value.map((tool) => tool.name)
)

const selected = computed(() => new Set(props.modelValue))

const readOnlyNames = computed(() =>
  readOnlyToolNames(availableTools.value, props.groups)
)

const areas = computed(() => {
  const result = []
  for (const group of props.groups) {
    const tools = availableTools.value.filter((t) => t.group === group.type)
    if (!tools.length) {
      continue
    }
    let area = result.find((a) => a.key === group.area)
    if (!area) {
      area = {
        key: group.area,
        label: AREA_LABELS[group.area]
          ? t(AREA_LABELS[group.area])
          : group.area,
        groups: [],
      }
      result.push(area)
    }
    area.groups.push({
      type: group.type,
      label: GROUP_LABELS[group.type]
        ? t(GROUP_LABELS[group.type])
        : group.title,
      tools,
    })
  }
  return result
})

function isDelete(tool) {
  return tool.name.startsWith('delete_') || tool.group.endsWith('_delete')
}

// Picked names, always in the order the API listed the tools.
function select(names) {
  const picked = new Set(names)
  emit(
    'update:modelValue',
    availableNames.value.filter((name) => picked.has(name))
  )
}

function toggle(names, value) {
  const picked = new Set(props.modelValue)
  for (const name of names) {
    if (value) {
      picked.add(name)
    } else {
      picked.delete(name)
    }
  }
  select([...picked])
}

function groupState(group) {
  const count = group.tools.filter((t) => selected.value.has(t.name)).length
  if (count === 0) {
    return 'none'
  }
  return count === group.tools.length ? 'all' : 'some'
}

function toggleGroup(group, value) {
  toggle(
    group.tools.map((tool) => tool.name),
    value
  )
}
</script>
