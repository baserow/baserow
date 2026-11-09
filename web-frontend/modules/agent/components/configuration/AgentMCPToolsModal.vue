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
              <span>{{ $t('agent.connectedAppChangesData') }}</span>
              <span>{{ $t('agent.toolAllow') }}</span>
            </span>
          </div>
          <div
            v-for="tool in tools"
            :key="tool.name"
            class="agent-tool-permissions__tool"
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
            </div>
            <span class="agent-mcp-tools__columns">
              <Checkbox
                class="agent-tool-permissions__allow"
                :model-value="picked[tool.name].changes_data"
                :disabled="!editable || tool.removed"
                @update:model-value="set(tool.name, 'changes_data', $event)"
                >{{ $t('agent.connectedAppChangesData') }}</Checkbox
              >
              <Checkbox
                class="agent-tool-permissions__allow"
                :model-value="picked[tool.name].enabled"
                :disabled="!editable || tool.removed"
                @update:model-value="set(tool.name, 'enabled', $event)"
                >{{ tool.title || tool.name }}</Checkbox
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
import { API_ERROR_CODE } from '@baserow/modules/agent/constants'

/**
 * Reviews the tools of an MCP server: which ones the Agent may call and which
 * change data. Saving marks every listed tool as reviewed, including changed
 * ones the editor leaves off.
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
const refreshing = ref(false)
const saving = ref(false)
const error = ref(null)

// Removed tools are listed last so the ones that can be used come first.
const tools = computed(() =>
  [...(server.value?.tools ?? [])].sort(
    (a, b) => Number(a.removed) - Number(b.removed)
  )
)

function reset(next) {
  // Choices the editor made survive a refresh; new tools start as stored.
  const previous = picked.value
  server.value = next
  picked.value = Object.fromEntries(
    next.tools.map((tool) => [
      tool.name,
      previous[tool.name] && !tool.changed_since_review
        ? previous[tool.name]
        : { enabled: tool.enabled, changes_data: tool.changes_data },
    ])
  )
}

function show(next) {
  picked.value = {}
  error.value = null
  reset(next)
  modal.value.show()
}

function set(name, key, value) {
  if (!props.editable) return
  picked.value = {
    ...picked.value,
    [name]: { ...picked.value[name], [key]: value },
  }
}

function readError(e) {
  if (!e.handler) throw e
  e.handler.handled()
  if (e.handler.code === API_ERROR_CODE.MCP_SERVER_REFUSED_CREDENTIAL) {
    return {
      title: t('agent.connectedAppRefusedTitle'),
      message: t('agent.connectedAppRefused'),
    }
  }
  if (e.handler.code === API_ERROR_CODE.MCP_SERVER_UNREACHABLE) {
    return {
      title: t('agent.connectedAppUnreachableTitle'),
      message: t('agent.connectedAppUnreachable'),
    }
  }
  return e.handler.getMessage()
}

async function refreshTools() {
  refreshing.value = true
  error.value = null
  try {
    reset(await props.refresh(server.value))
  } catch (e) {
    error.value = readError(e)
  } finally {
    refreshing.value = false
  }
}

async function done() {
  saving.value = true
  error.value = null
  try {
    await props.save(
      server.value,
      tools.value
        .filter((tool) => !tool.removed)
        .map((tool) => ({ name: tool.name, ...picked.value[tool.name] }))
    )
    modal.value.hide()
  } catch (e) {
    error.value = readError(e)
  } finally {
    saving.value = false
  }
}

defineExpose({ show })
</script>
