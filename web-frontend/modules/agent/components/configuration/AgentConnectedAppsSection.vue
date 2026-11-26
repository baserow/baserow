<template>
  <section class="agent-connected-apps" :aria-busy="loading">
    <div class="agent-actions__header">
      <h3>{{ $t('agent.connectedApps') }}</h3>
      <ButtonText
        v-if="editable"
        class="agent-connected-apps__add"
        type="primary"
        size="small"
        button-type="button"
        icon="iconoir-plus"
        :disabled="loading || Boolean(loadError)"
        @click="addDraft"
        >{{ $t('agent.connectedAppAdd') }}</ButtonText
      >
    </div>
    <p class="agent-connected-apps__description">
      {{ $t('agent.connectedAppsHelper') }}
    </p>
    <AgentCardListHeader
      v-if="cards.length"
      :all-expanded="allExpanded"
      @toggle-all="toggleAll"
    />
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
    <div v-else ref="list" class="agent-actions__list">
      <AgentMCPServerCard
        v-for="card in cards"
        :key="card.id"
        :data-card-id="card.id"
        :server="card.server"
        :expanded="expandedIds.has(card.id)"
        :editable="editable"
        :save="(server, values) => saveServer(card, server, values)"
        :remove="removeServer"
        :switching="Boolean(card.server) && patching.has(card.server.id)"
        :connect="connect"
        :disconnect="disconnect"
        :refresh="refreshTools"
        @toggle="toggle(card.id)"
        @switch="switchServer(card.server, $event)"
        @open-tools="(server) => toolsModal.show(server)"
        @saved="saved"
        @discard="discard(card.id)"
      />
    </div>
    <AgentMCPToolsModal
      ref="toolsModal"
      :agent-name="agent.name"
      :editable="editable"
      :refresh="refreshTools"
      :save="updateTools"
    />
  </section>
</template>

<script setup>
import { computed, inject, nextTick, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStore } from 'vuex'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import { useAgentMCPServers } from '@baserow/modules/agent/composables/useAgentMCPServers'
import { useExpandedItems } from '@baserow/modules/agent/composables/useExpandedItems'
import { mcpErrorMessage } from '@baserow/modules/agent/utils/mcp'
import AgentCardListHeader from '@baserow/modules/agent/components/configuration/AgentCardListHeader'
import AgentMCPServerCard from '@baserow/modules/agent/components/configuration/AgentMCPServerCard'
import AgentMCPToolsModal from '@baserow/modules/agent/components/configuration/AgentMCPToolsModal'

/**
 * The MCP servers an Agent may use, one card each, added, edited and removed
 * in place. A new card is a draft only this editor sees until it's saved; it
 * keeps its card once saved, so an error from its first sign-in stays shown.
 */
defineOptions({ inheritAttrs: false })
defineProps({ editable: Boolean })
// The web search setting depends on whether a reply offers any tools.
const emit = defineEmits(['reload'])
const { t } = useI18n()
const store = useStore()
const agent = inject('agentApplication')
const toolsModal = ref(null)
const list = ref(null)
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
} = useAgentMCPServers(agent, () => emit('reload'))

onMounted(load)

// Each draft has its own card id; `serverId` is set once it's saved.
const drafts = ref([])
let nextDraft = 0

const cards = computed(() => {
  const byId = new Map(servers.value.map((server) => [server.id, server]))
  const claimed = new Set(drafts.value.map((draft) => draft.serverId))
  return [
    ...servers.value
      .filter((server) => !claimed.has(server.id))
      .map((server) => ({ id: server.id, server })),
    ...drafts.value
      // A saved draft whose server was removed goes with it.
      .filter((draft) => draft.serverId === null || byId.has(draft.serverId))
      .map((draft) => ({
        id: draft.id,
        server: byId.get(draft.serverId) ?? null,
      })),
  ]
})
const { expandedIds, allExpanded, toggle, toggleAll } = useExpandedItems(cards)

async function addDraft() {
  const draft = { id: `draft-${++nextDraft}`, serverId: null }
  drafts.value = [...drafts.value, draft]
  expandedIds.add(draft.id)
  await nextTick()
  list.value
    ?.querySelector(`[data-card-id="${draft.id}"]`)
    ?.scrollIntoView?.({ block: 'start' })
}

function discard(id) {
  drafts.value = drafts.value.filter((draft) => draft.id !== id)
}

async function saveServer(card, server, values) {
  if (server) return await patch(server, values)
  const created = await create(values)
  // The draft's card shows the new server, so it isn't listed twice.
  drafts.value = drafts.value.map((draft) =>
    draft.id === card.id ? { ...draft, serverId: created.id } : draft
  )
  return created
}

function saved(server, { listTools, firstConnection = false }) {
  if (listTools) toolsModal.value.show(server, { firstConnection })
}

// One update per server at a time: each response carries the whole server,
// so an older one arriving last would undo a newer change on screen. Only the
// update itself waits, not the sign-in or tool listing after a save.
const patching = reactive(new Set())
const patches = new Map()

function patch(server, values) {
  const run = (patches.get(server.id) ?? Promise.resolve())
    .catch(() => {})
    .then(() => update(server, values))
  patches.set(server.id, run)
  patching.add(server.id)
  const settle = () => {
    if (patches.get(server.id) !== run) return
    patches.delete(server.id)
    patching.delete(server.id)
  }
  run.then(settle, settle)
  return run
}

async function switchServer(server, enabled) {
  if (patching.has(server.id)) return
  try {
    await patch(server, { enabled })
  } catch (error) {
    store.dispatch('toast/error', mcpErrorMessage(t, error))
  }
}

// The store drops the card before the request ends and brings it back if the
// request fails, so the failure is told here, not in the card.
async function removeServer(server) {
  try {
    await remove(server)
  } catch (error) {
    store.dispatch('toast/error', mcpErrorMessage(t, error))
  }
}
</script>
