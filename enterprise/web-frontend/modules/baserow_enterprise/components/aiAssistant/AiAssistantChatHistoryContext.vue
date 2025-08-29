<template>
  <Context ref="context" class="ai-assistant__chat-history-context">
    <ul class="context__menu ai-assistant__chat-history-menu">
      <li
        v-if="loading"
        class="context__menu-item ai-assistant__chat-history-loading"
      >
        <i
          class="iconoir-system-restart ai-assistant__chat-history-loading-icon"
        ></i>
        <span>{{ $t('aiAssistantChatHistoryContext.loading') }}</span>
      </li>

      <li
        v-else-if="!chats.length"
        class="context__menu-item ai-assistant__chat-history-empty"
      >
        <span>{{ $t('aiAssistantChatHistoryContext.empty') }}</span>
      </li>

      <template v-else>
        <li v-for="chat in chats" :key="chat.id" class="context__menu-item">
          <a
            class="context__menu-item-link ai-assistant__chat-history-link"
            @click="$emit('select-chat', chat)"
          >
            {{ chat.title }}
            <i
              v-if="chat.id === currentChatId"
              class="context__menu-active-icon iconoir-check"
            ></i>
          </a>
        </li>
      </template>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'AiAssistantChatHistoryContext',
  mixins: [context],
  props: {
    currentChatId: {
      type: String,
      default: null,
    },
    chats: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
