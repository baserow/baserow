<template>
  <Context ref="context" class="ai-assistant__history-context">
    <ul class="context__menu ai-assistant__history-menu">
      <!-- Loading state -->
      <li
        v-if="loading"
        class="context__menu-item ai-assistant__history-chat-loading"
      >
        <i
          class="iconoir-system-restart ai-assistant__history-chat-loading-icon"
        ></i>
        <span>Loading chats...</span>
      </li>

      <li
        v-else-if="!chats.length"
        class="context__menu-item ai-assistant__history-empty"
      >
        <span>No recent chats</span>
      </li>

      <template v-else>
        <li
          v-for="(chat, index) in chats"
          :key="chat.uid"
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            @click="$emit('select-chat', chat)"
          >
            {{
              chat.title ||
              (index > 0 ? 'Chat ' + chat.uid.split('-').at(-1) : '&nbsp;')
            }}
          </a>
        </li>
      </template>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'AiAssistantHistoryContext',
  mixins: [context],
  props: {
    chats: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['select-chat'],
}
</script>
