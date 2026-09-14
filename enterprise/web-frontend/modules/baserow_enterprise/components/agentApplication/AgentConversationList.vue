<template>
  <div class="agent-conversation-list">
    <div class="agent-conversation-list__scroll">
      <template v-if="pinnedChats.length > 0">
        <div class="agent-conversation-list__section-title">
          {{ $t('agentConversationList.pinned') }}
        </div>
        <ul class="agent-conversation-list__items">
          <AgentConversationListItem
            v-for="chat in pinnedChats"
            :key="chat.id"
            :application="application"
            :chat="chat"
            :active="isCurrent(chat)"
            :loading="isLoading(chat)"
            @select="selectChat(chat)"
          />
        </ul>
      </template>
      <div class="agent-conversation-list__section-title">
        {{ $t('agentConversationList.recent') }}
      </div>
      <div
        v-if="recentChats.length === 0"
        class="agent-conversation-list__empty"
      >
        {{ $t('agentConversationList.empty') }}
      </div>
      <ul v-else class="agent-conversation-list__items">
        <AgentConversationListItem
          v-for="chat in recentChats"
          :key="chat.id"
          :application="application"
          :chat="chat"
          :active="isCurrent(chat)"
          :loading="isLoading(chat)"
          @select="selectChat(chat)"
        />
      </ul>
      <ButtonText
        v-if="hasMore"
        class="agent-conversation-list__load-more"
        icon="iconoir-nav-arrow-down"
        :loading="loading"
        @click="loadMore"
      >
        {{ $t('agentConversationList.loadMore') }}
      </ButtonText>
    </div>
    <div v-if="canRunChat" class="agent-conversation-list__footer">
      <Button
        type="secondary"
        icon="iconoir-plus"
        full-width
        @click="newConversation"
      >
        {{ $t('agentConversationList.newConversation') }}
      </Button>
    </div>
  </div>
</template>

<script>
import { defineComponent, computed } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#imports'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AgentConversationListItem from '@baserow_enterprise/components/agentApplication/AgentConversationListItem'

export default defineComponent({
  name: 'AgentConversationList',
  components: { AgentConversationListItem },
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    const store = useStore()
    const { $hasPermission } = useNuxtApp()

    const canRunChat = computed(() =>
      $hasPermission(
        'agent_application.run_chat',
        props.application,
        props.application.workspace.id
      )
    )
    const pinnedChats = computed(
      () => store.getters['agentHistory/getPinnedChats']
    )
    const recentChats = computed(
      () => store.getters['agentHistory/getRecentChats']
    )
    const currentChatUuid = computed(
      () => store.getters['agentChat/getCurrentChatUuid']
    )
    const isCurrent = (chat) => chat.uuid === currentChatUuid.value

    const hasMore = computed(() => store.getters['agentHistory/hasMore'])
    const loading = computed(() => store.getters['agentHistory/isLoading'])
    const loadMore = async () => {
      try {
        await store.dispatch('agentHistory/fetchMore', {
          applicationId: props.application.id,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }

    const loadingChatUuid = computed(
      () => store.getters['agentChat/getLoadingChatUuid']
    )
    const isLoading = (chat) => chat.uuid === loadingChatUuid.value
    const selectChat = async (chat) => {
      if (isLoading(chat) || isCurrent(chat)) {
        return
      }
      try {
        await store.dispatch('agentChat/openConversation', {
          applicationId: props.application.id,
          chatUuid: chat.uuid,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }
    const newConversation = () => {
      store.dispatch('agentChat/newConversation')
    }

    return {
      canRunChat,
      pinnedChats,
      recentChats,
      hasMore,
      loading,
      isLoading,
      isCurrent,
      selectChat,
      newConversation,
      loadMore,
    }
  },
})
</script>
