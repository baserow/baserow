<template>
  <Modal ref="modal" small>
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
              <div
                v-if="tool.description"
                class="agent-tool-permissions__tool-description agent-mcp-tools__tool-description"
                :title="tool.description"
              >
                {{ tool.description }}
              </div>
              <ButtonText
                v-if="hasSchema(tool)"
                class="agent-mcp-tools__parameters-toggle"
                size="small"
                :icon="
                  expanded[tool.name]
                    ? 'iconoir-nav-arrow-down'
                    : 'iconoir-nav-arrow-right'
                "
                @click="toggle(tool.name)"
              >
                {{
                  parameters(tool).length
                    ? $t(
                        'agent.connectedAppToolParameters',
                        { count: parameters(tool).length },
                        parameters(tool).length
                      )
                    : $t('agent.connectedAppToolSchema')
                }}
              </ButtonText>
              <ul
                v-if="expanded[tool.name] && parameters(tool).length"
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
              <details
                v-if="expanded[tool.name]"
                class="agent-mcp-tools__schema"
              >
                <summary>{{ $t('agent.connectedAppToolSchema') }}</summary>
                <pre>{{ JSON.stringify(tool.input_schema, null, 2) }}</pre>
              </details>
            </div>
            <span class="agent-mcp-tools__columns">
              <Checkbox
                class="agent-tool-permissions__allow"
                :model-value="choice(tool).enabled"
                :disabled="!editable || tool.removed"
                @update:model-value="set(tool, 'enabled', $event)"
                >{{ tool.title || tool.name }}</Checkbox
              >
              <Checkbox
                class="agent-tool-permissions__ask-first"
                :model-value="choice(tool).ask_first"
                :disabled="!editable || tool.removed || !choice(tool).enabled"
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
            :disabled="!editable || !tools.length"
            :loading="saving"
            @click="done"
          >
            {{ $t('agent.toolsDone') }}
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

function toggle(name) {
  expanded.value = { ...expanded.value, [name]: !expanded.value[name] }
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

function show(next) {
  opening++
  picked.value = {}
  expanded.value = {}
  error.value = null
  refreshing.value = false
  saving.value = false
  reset(next)
  modal.value.show()
}

function set(tool, key, value) {
  if (!props.editable) return
  picked.value = {
    ...picked.value,
    [tool.name]: { ...choice(tool), [key]: value },
  }
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
      tools.value
        .filter((tool) => !tool.removed)
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
