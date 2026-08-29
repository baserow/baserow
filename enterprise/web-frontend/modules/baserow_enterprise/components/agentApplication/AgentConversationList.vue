<template>
  <div class="agent-conversation-list">
    <template v-if="runningChats.length > 0">
      <div class="agent-conversation-list__section-title">
        {{ $t('agentConversationList.running') }}
      </div>
      <ul class="agent-conversation-list__items">
        <li
          v-for="chat in runningChats"
          :key="chat.id"
          class="agent-conversation-list__item"
          :class="{
            'agent-conversation-list__item--active': isCurrent(chat),
          }"
          @click="selectChat(chat)"
        >
          <i
            class="agent-conversation-list__item-icon"
            :class="sourceIcon(chat)"
          ></i>
          <div class="agent-conversation-list__item-content">
            <div class="agent-conversation-list__item-title">
              {{ chat.title || $t('agentConversationList.untitled') }}
            </div>
            <div class="agent-conversation-list__item-meta">
              <span>{{ relativeTime(chat) }}</span>
              <span
                v-if="chatTokens(chat) !== null"
                class="agent-conversation-list__item-tokens"
                >{{
                  $t('agentConversationList.tokens', {
                    amount: chatTokens(chat),
                  })
                }}</span
              >
            </div>
          </div>
          <span
            class="agent-conversation-list__item-status"
            :class="statusModifier(chat)"
          ></span>
          <a
            v-if="canCancelChat"
            class="agent-conversation-list__item-stop"
            :title="$t('agentConversationList.stop')"
            @click.stop="stopChat(chat)"
          >
            <i class="iconoir-square"></i>
          </a>
        </li>
      </ul>
    </template>
    <div class="agent-conversation-list__section-title">
      {{ $t('agentConversationList.recent') }}
    </div>
    <div v-if="recentChats.length === 0" class="agent-conversation-list__empty">
      {{ $t('agentConversationList.empty') }}
    </div>
    <ul v-else class="agent-conversation-list__items">
      <li
        v-for="chat in recentChats"
        :key="chat.id"
        class="agent-conversation-list__item"
        :class="{
          'agent-conversation-list__item--active': isCurrent(chat),
        }"
        @click="selectChat(chat)"
      >
        <i
          class="agent-conversation-list__item-icon"
          :class="sourceIcon(chat)"
        ></i>
        <div class="agent-conversation-list__item-content">
          <div class="agent-conversation-list__item-title">
            {{ chat.title || $t('agentConversationList.untitled') }}
          </div>
          <div class="agent-conversation-list__item-meta">
            <span>{{ relativeTime(chat) }}</span>
            <span
              v-if="chatTokens(chat) !== null"
              class="agent-conversation-list__item-tokens"
              >{{
                $t('agentConversationList.tokens', {
                  amount: chatTokens(chat),
                })
              }}</span
            >
          </div>
        </div>
        <span
          v-if="chat.status === 'error' || chat.status === 'awaiting_approval'"
          class="agent-conversation-list__item-status"
          :class="statusModifier(chat)"
          :title="
            chat.status === 'awaiting_approval'
              ? $t('agentConversationList.awaitingApproval')
              : null
          "
        ></span>
      </li>
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
</template>

<script>
import { defineComponent, computed } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#imports'
import moment from '@baserow/modules/core/moment'
import { notifyIf } from '@baserow/modules/core/utils/error'

const SOURCE_ICONS = {
  manual: 'iconoir-chat-bubble-empty',
  trigger: 'iconoir-flash',
  setup: 'iconoir-sparks',
}

function formatTokens(total) {
  if (total >= 1000000) {
    return `${parseFloat((total / 1000000).toFixed(1))}M`
  }
  if (total >= 1000) {
    return `${parseFloat((total / 1000).toFixed(1))}k`
  }
  return `${total}`
}

export default defineComponent({
  name: 'AgentConversationList',
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    const store = useStore()
    const { $hasPermission } = useNuxtApp()

    const canCancelChat = computed(() =>
      $hasPermission(
        'agent_application.cancel_chat',
        props.application,
        props.application.workspace.id
      )
    )

    const runningChats = computed(
      () => store.getters['agentHistory/getRunningChats']
    )
    const recentChats = computed(() =>
      store.getters['agentHistory/getChats'].filter(
        (chat) => !runningChats.value.includes(chat)
      )
    )
    const currentChatUuid = computed(
      () => store.getters['agentChat/getCurrentChatUuid']
    )

    const isCurrent = (chat) => chat.uuid === currentChatUuid.value

    const sourceIcon = (chat) =>
      SOURCE_ICONS[chat.source] || SOURCE_ICONS.manual

    const statusModifier = (chat) =>
      `agent-conversation-list__item-status--${chat.status.replace('_', '-')}`

    const relativeTime = (chat) =>
      moment(chat.updated_on || chat.created_on).fromNow()

    const chatTokens = (chat) => {
      const total =
        (chat.total_input_tokens || 0) + (chat.total_output_tokens || 0)
      return total > 0 ? formatTokens(total) : null
    }

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

    const selectChat = async (chat) => {
      try {
        await store.dispatch('agentChat/openConversation', {
          applicationId: props.application.id,
          chatUuid: chat.uuid,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }

    const stopChat = async (chat) => {
      try {
        await store.dispatch('agentChat/cancel', { chatUuid: chat.uuid })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }

    return {
      runningChats,
      recentChats,
      canCancelChat,
      hasMore,
      loading,
      isCurrent,
      sourceIcon,
      statusModifier,
      relativeTime,
      chatTokens,
      selectChat,
      stopChat,
      loadMore,
    }
  },
})
</script>
