<template>
  <section class="agent-channels" :aria-busy="loading">
    <div class="agent-channels__header">
      <h3 class="agent-channels__title">{{ $t('agentChannels.section') }}</h3>
      <ButtonText
        v-if="editable"
        type="primary"
        size="small"
        button-type="button"
        :icon="licensed ? 'iconoir-plus' : 'iconoir-lock'"
        class="agent-channels__add"
        :disabled="creating || loading || loadError"
        :loading="creating"
        @click="add"
      >
        {{ $t('agentChannels.addPublicChat') }}
      </ButtonText>
    </div>
    <AgentCardListHeader
      v-if="!loading && !loadError && channels.length"
      :all-expanded="allExpanded"
      @toggle-all="toggleAll"
    />
    <div v-if="loading" class="skeleton" aria-hidden="true">
      <SkeletonBlock width="100%" height="120px" />
    </div>
    <Alert v-else-if="loadError" type="error">
      {{ $t('agentChannels.loadError') }}
      <template #actions
        ><Button
          type="secondary"
          size="small"
          button-type="button"
          @click="retryLoad"
          >{{ $t('action.retry') }}</Button
        ></template
      >
    </Alert>
    <p v-else-if="!channels.length" class="agent-channels__empty">
      {{ $t('agentChannels.empty') }}
    </p>
    <div v-else ref="list" class="agent-channels__list">
      <AgentPublicChatCard
        v-for="channel in channels"
        :key="channel.id"
        :data-card-id="channel.id"
        :channel="channel"
        :agent-name="agent?.name || ''"
        :expanded="expandedIds.has(channel.id)"
        :editable="editable"
        :licensed="licensed"
        :saving="savingIds.has(channel.id)"
        :save-password="(password) => savePassword(channel, password)"
        @toggle="toggle(channel.id)"
        @update="updateChannel(channel, $event)"
        @delete="deleteChannel(channel)"
      />
    </div>
    <PaidFeaturesModal
      v-if="workspace"
      ref="paywall"
      :workspace="workspace"
      initial-selected-type="rbac"
    />
  </section>
</template>

<script setup>
import { computed, inject, ref, watch } from 'vue'
import { useStore } from 'vuex'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import AgentCardListHeader from '@baserow/modules/agent/components/configuration/AgentCardListHeader'
import { useAgentCardList } from '@baserow/modules/agent/composables/useExpandedItems'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import AgentPublicChatCard from '@baserow_enterprise/components/agent/AgentPublicChatCard'
import { useAgentChannels } from '@baserow_enterprise/composables/useAgentChannels'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  /** The Channels section type, which tells whether public chats can be added. */
  sectionType: { type: Object, required: true },
  /** Whether the user may add, change and delete channels. */
  editable: Boolean,
})
const store = useStore()
const agent = inject('agentApplication')
const templatePreview = inject('agentTemplatePreview', false)
const paywall = ref(null)
const workspace = computed(() =>
  agent.value ? store.getters['workspace/get'](agent.value.workspace.id) : null
)
const licensed = computed(() => props.sectionType.isLicensed(workspace.value))
const {
  channels,
  loading,
  loadError,
  savingIds,
  retryLoad,
  createChannel,
  updateChannel,
  savePassword,
  deleteChannel,
} = useAgentChannels(agent, { load: !templatePreview })
const { expandedIds, allExpanded, toggle, toggleAll, list, creating, addItem } =
  useAgentCardList(channels, createChannel)
let initializedFor = null
watch([loading, () => agent.value?.id], ([busy, id]) => {
  if (busy || loadError.value || !id || initializedFor === id) return
  initializedFor = id
  if (channels.value.length === 1) expandedIds.add(channels.value[0].id)
})

function add() {
  if (licensed.value) addItem()
  else paywall.value?.show()
}
</script>
