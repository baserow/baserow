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
        :aria-haspopup="licensed ? 'menu' : null"
        @click="add($event.currentTarget)"
      >
        {{ $t('agentChannels.addChannel') }}
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
      <AgentChannelCard
        v-for="channel in channels"
        :key="channel.id"
        :data-card-id="channel.id"
        :channel="channel"
        :channel-type="channelTypeOf(channel)"
        :form-props="formPropsOf(channel)"
        :agent-name="agent?.name || ''"
        :expanded="expandedIds.has(channel.id)"
        :editable="editable"
        :licensed="licensed"
        :saving="savingIds.has(channel.id)"
        @toggle="toggle(channel.id)"
        @update="updateChannel(channel, $event)"
        @delete="deleteChannel(channel)"
      />
    </div>
    <Context ref="picker" class="agent-channels__picker" @shown="focusMenu">
      <MenuList
        ref="menu"
        :items="pickerItems"
        @select="pick"
        @close="picker.hide()"
      />
    </Context>
    <PaidFeaturesModal
      v-if="workspace"
      ref="paywall"
      :workspace="workspace"
      initial-selected-type="rbac"
    />
  </section>
</template>

<script setup>
import { computed, inject, nextTick, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import Context from '@baserow/modules/core/components/Context'
import MenuList from '@baserow/modules/core/components/MenuList'
import AgentCardListHeader from '@baserow/modules/agent/components/configuration/AgentCardListHeader'
import { useAgentCardList } from '@baserow/modules/agent/composables/useExpandedItems'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import AgentChannelCard from '@baserow_enterprise/components/agent/AgentChannelCard'
import { useAgentChannels } from '@baserow_enterprise/composables/useAgentChannels'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  /** The Channels section type, which tells whether channels can be added. */
  sectionType: { type: Object, required: true },
  /** Whether the user may add, change and delete channels. */
  editable: Boolean,
})
const store = useStore()
const { $registry } = useNuxtApp()
const agent = inject('agentApplication')
const templatePreview = inject('agentTemplatePreview', false)
const paywall = ref(null)
const picker = ref(null)
const menu = ref(null)
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
const channelTypeOf = (channel) =>
  $registry.get('agentChannelType', channel.type)
const formPropsOf = (channel) =>
  channelTypeOf(channel).getFormProps({
    savePassword: (password) => savePassword(channel, password),
  })
const pickerItems = computed(() =>
  $registry.getOrderedList('agentChannelType').map((channelType) => ({
    id: channelType.getType(),
    value: channelType.getType(),
    label: channelType.name,
    description: channelType.description,
    icon: channelType.icon,
  }))
)
const { expandedIds, allExpanded, toggle, toggleAll, list, creating, addItem } =
  useAgentCardList(channels, (type) => createChannel(type))
let initializedFor = null
watch([loading, () => agent.value?.id], ([busy, id]) => {
  if (busy || loadError.value || !id || initializedFor === id) return
  initializedFor = id
  if (channels.value.length === 1) expandedIds.add(channels.value[0].id)
})

function add(target) {
  if (licensed.value) picker.value.toggle(target, 'bottom', 'right', 4)
  else paywall.value?.show()
}

async function focusMenu() {
  await nextTick()
  menu.value?.focus()
}

function pick(item) {
  picker.value.hide()
  addItem(item.value)
}
</script>
