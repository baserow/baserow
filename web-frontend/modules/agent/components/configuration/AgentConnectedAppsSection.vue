<template>
  <div class="agent-connected-apps">
    <p class="agent-connected-apps__description">
      {{ $t('agent.connectedAppsHelper') }}
    </p>
    <div v-if="loading && !servers.length" class="skeleton" aria-hidden="true">
      <SkeletonBlock height="56px" />
    </div>
    <Alert v-else-if="loadError" type="error">
      {{ $t('agent.connectedAppsLoadError') }}
      <template #actions>
        <Button type="secondary" size="small" @click="load">
          {{ $t('action.retry') }}
        </Button>
      </template>
    </Alert>
    <template v-else>
      <div
        v-for="server in servers"
        :key="server.id"
        class="agent-connected-apps__server"
      >
        <i class="iconoir-server agent-connected-apps__server-icon"></i>
        <div class="agent-connected-apps__server-content">
          <div class="agent-connected-apps__server-name">{{ server.name }}</div>
          <div class="agent-connected-apps__server-meta">
            <Icon
              v-if="changedCount(server)"
              icon="iconoir-warning-triangle"
              type="warning"
              size="small"
            />
            {{ summary(server) }}
          </div>
        </div>
        <ButtonText
          type="secondary"
          size="small"
          @click="toolsModal.show(server)"
        >
          {{ $t('agent.connectedAppTools') }}
        </ButtonText>
        <ButtonIcon
          v-if="editable"
          icon="iconoir-edit-pencil"
          size="small"
          :aria-label="$t('agent.connectedAppEdit', { name: server.name })"
          @click="serverModal.show(server)"
        />
      </div>
      <Button
        v-if="editable"
        class="agent-connected-apps__add"
        type="secondary"
        icon="iconoir-plus"
        @click="serverModal.show()"
      >
        {{ $t('agent.connectedAppAdd') }}
      </Button>
    </template>
    <AgentMCPServerModal
      ref="serverModal"
      :save="saveServer"
      :remove="remove"
      @created="toolsModal.show($event)"
    />
    <AgentMCPToolsModal
      ref="toolsModal"
      :agent-name="agent.name"
      :editable="editable"
      :refresh="refreshTools"
      :save="updateTools"
    />
  </div>
</template>

<script setup>
import { inject, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import ButtonIcon from '@baserow/modules/core/components/ButtonIcon'
import Icon from '@baserow/modules/core/components/Icon'
import { useAgentMCPServers } from '@baserow/modules/agent/composables/useAgentMCPServers'
import AgentMCPServerModal from '@baserow/modules/agent/components/configuration/AgentMCPServerModal'
import AgentMCPToolsModal from '@baserow/modules/agent/components/configuration/AgentMCPToolsModal'

/** Lists the MCP servers an Agent may use, and adds, edits and reviews them. */
defineOptions({ inheritAttrs: false })
defineProps({ editable: Boolean })
const { t } = useI18n()
const agent = inject('agentApplication')
const serverModal = ref(null)
const toolsModal = ref(null)
const {
  servers,
  loading,
  loadError,
  load,
  create,
  update,
  remove,
  refreshTools,
  updateTools,
} = useAgentMCPServers(agent)

onMounted(load)

const changedCount = (server) =>
  server.tools.filter((tool) => tool.changed_since_review).length

function summary(server) {
  const changed = changedCount(server)
  if (changed)
    return t('agent.connectedAppChanged', { count: changed }, changed)
  const tools = server.tools.filter((tool) => !tool.removed)
  if (!tools.length) return t('agent.connectedAppNoTools')
  return t('agent.toolsOn', {
    count: tools.filter((tool) => tool.enabled).length,
    total: tools.length,
  })
}

/** Creating a server lists its tools straight away, so they can be reviewed. */
async function saveServer(server, values) {
  if (server) return await update(server, values)
  const created = await create(values)
  try {
    return await refreshTools(created)
  } catch {
    // The tools modal shows the error and can try again.
    return created
  }
}
</script>
