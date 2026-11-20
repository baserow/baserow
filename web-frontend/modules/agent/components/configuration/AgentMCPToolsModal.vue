<template>
  <Modal ref="modal" wide>
    <template #content>
      <template v-if="server">
        <h2 class="box__title">
          {{ $t('agent.connectedAppToolsTitle', { name: server.name }) }}
        </h2>
        <div class="agent-mcp-tools__head">
          <p class="agent-tool-permissions__description">
            {{ $t('agent.connectedAppToolsDescription', { name: agentName }) }}
          </p>
          <Button
            v-if="editable"
            type="secondary"
            size="small"
            icon="iconoir-refresh"
            :loading="refreshing"
            :disabled="saving"
            @click="refreshTools"
          >
            {{ $t('agent.connectedAppRefresh') }}
          </Button>
        </div>
        <Alert v-if="error" type="error" class="margin-bottom-2">
          <template #title>{{ error.title }}</template>
          {{ error.message }}
        </Alert>
        <p v-if="!tools.length" class="agent-mcp-tools__empty">
          {{ $t('agent.connectedAppNoTools') }}
        </p>
        <div v-else class="agent-tool-permissions__list">
          <div class="agent-tool-permissions__list-head">
            <span>{{ $t('agent.connectedAppTool') }}</span>
            <Button
              v-if="editable && availableTools.length"
              type="secondary"
              size="small"
              class="agent-mcp-tools__select-all"
              :disabled="saving || refreshing"
              @click="selectAll(!allSelected)"
              >{{
                $t(
                  allSelected
                    ? 'agent.deselectAllTools'
                    : 'agent.selectAllTools'
                )
              }}</Button
            >
            <span class="agent-mcp-tools__columns">
              <span>{{ $t('agent.toolAllow') }}</span>
              <span>{{ $t('agent.toolAskFirst') }}</span>
            </span>
          </div>
          <div
            v-for="tool in tools"
            :key="tool.name"
            class="agent-tool-permissions__tool agent-mcp-tools__tool"
            :class="{ 'agent-mcp-tools__tool--removed': tool.removed }"
          >
            <div class="agent-mcp-tools__tool-content">
              <div class="agent-tool-permissions__tool-name">
                {{ tool.title || tool.name }}
                <Badge
                  v-if="tool.changed_since_review"
                  color="yellow"
                  size="small"
                >
                  {{ $t('agent.connectedAppToolChanged') }}
                </Badge>
                <Badge v-if="tool.removed" size="small">
                  {{ $t('agent.connectedAppToolRemoved') }}
                </Badge>
              </div>
              <ButtonText
                v-if="tool.description"
                v-bind="disclosure(tool, 'description')"
              >
                {{ $t('agent.toolDescription') }}
              </ButtonText>
              <p
                v-if="tool.description && isOpen(tool, 'description')"
                class="agent-mcp-tools__description"
              >
                {{ tool.description }}
              </p>
              <ButtonText
                v-if="parameters(tool).length"
                v-bind="disclosure(tool, 'parameters')"
              >
                {{
                  $t(
                    'agent.connectedAppToolParameters',
                    { count: parameters(tool).length },
                    parameters(tool).length
                  )
                }}
              </ButtonText>
              <ul
                v-if="parameters(tool).length && isOpen(tool, 'parameters')"
                class="agent-mcp-tools__parameters"
              >
                <li
                  v-for="parameter in parameters(tool)"
                  :key="parameter.name"
                  class="agent-mcp-tools__parameter"
                >
                  <code>{{ parameter.name }}</code>
                  <span class="agent-mcp-tools__parameter-type">{{
                    parameter.type
                  }}</span>
                  <span
                    v-if="parameter.required"
                    class="agent-mcp-tools__parameter-required"
                    >{{ $t('agent.connectedAppToolParameterRequired') }}</span
                  >
                  <span
                    v-if="parameter.description"
                    class="agent-mcp-tools__parameter-description"
                    >{{ parameter.description }}</span
                  >
                </li>
              </ul>
              <ButtonText
                v-if="hasSchema(tool)"
                v-bind="disclosure(tool, 'schema')"
              >
                {{ $t('agent.connectedAppToolSchema') }}
              </ButtonText>
              <pre
                v-if="hasSchema(tool) && isOpen(tool, 'schema')"
                class="agent-mcp-tools__schema"
                >{{ JSON.stringify(tool.input_schema, null, 2) }}</pre
              >
            </div>
            <span class="agent-mcp-tools__columns">
              <Checkbox
                class="agent-tool-permissions__allow"
                :model-value="choice(tool).enabled"
                :disabled="!editable || saving || refreshing || tool.removed"
                @update:model-value="set(tool, 'enabled', $event)"
                >{{ tool.title || tool.name }}</Checkbox
              >
              <Checkbox
                class="agent-tool-permissions__ask-first"
                :model-value="choice(tool).ask_first"
                :disabled="
                  !editable ||
                  saving ||
                  refreshing ||
                  tool.removed ||
                  !choice(tool).enabled
                "
                @update:model-value="set(tool, 'ask_first', $event)"
                >{{
                  $t('agent.toolAskFirstLabel', {
                    name: tool.title || tool.name,
                  })
                }}</Checkbox
              >
            </span>
          </div>
        </div>
        <div class="agent-tool-permissions__actions">
          <Button type="secondary" @click="modal.hide()">
            {{ $t('action.cancel') }}
          </Button>
          <Button
            type="primary"
            :disabled="!editable || refreshing || !tools.length"
            :loading="saving"
            @click="done"
          >
            {{ $t('action.save') }}
          </Button>
        </div>
      </template>
    </template>
  </Modal>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import { mcpErrorMessage } from '@baserow/modules/agent/utils/mcp'

/**
 * Reviews the tools of an MCP server: which ones the Agent may call, which
 * wait for the owner's approval, and the parameters the model fills in. Saving marks every
 * listed tool as reviewed, including changed ones the editor leaves off.
 */
const props = defineProps({
  agentName: { type: String, required: true },
  editable: Boolean,
  refresh: { type: Function, required: true },
  save: { type: Function, required: true },
})
const { t } = useI18n()

const modal = ref(null)
const server = ref(null)
const picked = ref({})
const expanded = ref({})
const refreshing = ref(false)
const saving = ref(false)
const error = ref(null)
// Bumped each time the modal opens, so a request that finishes after the
// editor moved on to another server or opening is ignored.
let opening = 0

// Removed tools are listed last so the ones that can be used come first.
const tools = computed(() =>
  [...(server.value?.tools ?? [])].sort(
    (a, b) => Number(a.removed) - Number(b.removed)
  )
)

/** The tool's top-level parameters, as its input schema describes them. */
function parameters(tool) {
  const schema = tool.input_schema ?? {}
  const required = new Set(schema.required ?? [])
  return Object.entries(schema.properties ?? {}).map(([name, property]) => ({
    name,
    type: [property?.type ?? 'any'].flat().join(' | '),
    description: property?.description ?? '',
    required: required.has(name),
  }))
}

/**
 * Whether the tool takes input. Only top-level parameters are summed up; the
 * full schema shows the rest, such as allowed values and nested objects.
 */
function hasSchema(tool) {
  return Object.keys(tool.input_schema ?? {}).some((key) => key !== 'type')
}

const isOpen = (tool, part) => Boolean(expanded.value[`${tool.name}:${part}`])

function toggle(tool, part) {
  const key = `${tool.name}:${part}`
  expanded.value = { ...expanded.value, [key]: !expanded.value[key] }
}

/** Props and click handler for one collapsible part of a tool. */
function disclosure(tool, part) {
  const open = isOpen(tool, part)
  return {
    class: 'agent-mcp-tools__toggle',
    size: 'small',
    'aria-expanded': open,
    icon: open ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right',
    onClick: () => toggle(tool, part),
  }
}

/**
 * What the editor picked for the tool as it's listed now. A pick is kept with
 * the definition it was made for: when a refresh, here or by another editor,
 * changes the tool, it shows and saves as stored until picked again.
 */
function choice(tool) {
  const entry = picked.value[tool.name]
  return entry?.definition_hash === tool.definition_hash
    ? entry
    : {
        definition_hash: tool.definition_hash,
        enabled: tool.enabled,
        ask_first: tool.ask_first,
      }
}

function reset(next) {
  server.value = next
}

function show(next, { firstConnection = false } = {}) {
  opening++
  picked.value = {}
  expanded.value = {}
  error.value = null
  refreshing.value = false
  saving.value = false
  reset(next)
  if (firstConnection) selectAll(true)
  modal.value.show()
}

function set(tool, key, value) {
  if (!props.editable) return
  picked.value = {
    ...picked.value,
    [tool.name]: { ...choice(tool), [key]: value },
  }
}

const availableTools = computed(() =>
  tools.value.filter((tool) => !tool.removed)
)
const allSelected = computed(() =>
  availableTools.value.every((tool) => choice(tool).enabled)
)

function selectAll(enabled) {
  if (!props.editable) return
  picked.value = Object.fromEntries(
    availableTools.value.map((tool) => [
      tool.name,
      { ...choice(tool), enabled },
    ])
  )
}

async function refreshTools() {
  const current = opening
  refreshing.value = true
  error.value = null
  try {
    const refreshed = await props.refresh(server.value)
    if (current === opening) reset(refreshed)
  } catch (e) {
    const message = mcpErrorMessage(t, e)
    if (current === opening) error.value = message
  } finally {
    if (current === opening) refreshing.value = false
  }
}

async function done() {
  const current = opening
  saving.value = true
  error.value = null
  try {
    await props.save(
      server.value,
      availableTools.value
        // The server keeps a tool that changed since its pick as it is.
        .map((tool) => ({ name: tool.name, ...choice(tool) }))
    )
    if (current === opening) modal.value.hide()
  } catch (e) {
    const message = mcpErrorMessage(t, e)
    if (current === opening) error.value = message
  } finally {
    if (current === opening) saving.value = false
  }
}

defineExpose({ show })
</script>
