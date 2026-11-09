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
              v-if="changedCount(server) || needsAccount(server)"
              icon="iconoir-warning-triangle"
              type="warning"
              size="small"
            />
            {{ summary(server) }}
          </div>
        </div>
        <ButtonText
          v-if="needsAccount(server) && editable"
          size="small"
          :loading="connecting === server.id"
          @click="connectServer(server)"
        >
          {{ $t('agent.connectedAppSignIn') }}
        </ButtonText>
        <ButtonText
          v-else
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
      :connect="connect"
      :disconnect="disconnect"
      :refresh="refreshTools"
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
import { useStore } from 'vuex'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import ButtonIcon from '@baserow/modules/core/components/ButtonIcon'
import Icon from '@baserow/modules/core/components/Icon'
import {
  MCPSignInError,
  openSignInPopup,
  useAgentMCPServers,
} from '@baserow/modules/agent/composables/useAgentMCPServers'
import { MCP_AUTH_TYPE } from '@baserow/modules/agent/constants'
import AgentMCPServerModal from '@baserow/modules/agent/components/configuration/AgentMCPServerModal'
import AgentMCPToolsModal from '@baserow/modules/agent/components/configuration/AgentMCPToolsModal'

/** Lists the MCP servers an Agent may use, and adds, edits and reviews them. */
defineOptions({ inheritAttrs: false })
defineProps({ editable: Boolean })
const { t } = useI18n()
const store = useStore()
const agent = inject('agentApplication')
const connecting = ref(null)
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
  connect,
  disconnect,
} = useAgentMCPServers(agent)

onMounted(load)

const changedCount = (server) =>
  server.tools.filter((tool) => tool.changed_since_review).length

const needsAccount = (server) =>
  server.auth_type === MCP_AUTH_TYPE.OAUTH && !server.oauth_connected

function summary(server) {
  if (needsAccount(server)) return t('agent.connectedAppNotConnected')
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

async function saveServer(server, values) {
  return server ? await update(server, values) : await create(values)
}

async function connectServer(server) {
  const popup = openSignInPopup()
  if (!popup) {
    store.dispatch('toast/error', {
      title: t('agent.connectedAppSignInFailedTitle'),
      message: t('agent.connectedAppPopupBlocked'),
    })
    return
  }
  connecting.value = server.id
  try {
    toolsModal.value.show(await connect(server, popup))
  } catch (error) {
    popup?.close()
    if (error instanceof MCPSignInError) {
      store.dispatch('toast/error', {
        title: t('agent.connectedAppSignInFailedTitle'),
        message: error.reason || t('agent.connectedAppSignInFailed'),
      })
    } else {
      error.handler?.notifyIf()
      if (!error.handler) throw error
    }
  } finally {
    connecting.value = null
  }
}
</script>
