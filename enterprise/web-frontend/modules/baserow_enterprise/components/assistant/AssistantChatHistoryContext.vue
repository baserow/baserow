<template>
  <Context ref="context" max-height-if-outside-viewport class="select">
    <div v-if="loading" class="assistant__chat-history-spacer context--loading">
      <div class="loading"></div>
    </div>
    <div
      v-else-if="!chats.length"
      class="assistant__chat-history-spacer context__description"
    >
      {{ $t('assistantChatHistoryContext.empty') }}
    </div>
    <ul
      v-else
      ref="dropdown"
      v-auto-overflow-scroll
      class="select__items select__items--no-max-height"
    >
      <li
        v-for="chat in chats"
        :key="chat.id"
        class="select__item select__item--no-options"
        :class="{
          active: chat.id === currentChatId,
          'select__item--loading': chat.loading,
        }"
      >
        <a class="select__item-link" @click="$emit('select-chat', chat)">
          <div class="select__item-name">
            <span class="select__item-name-text">
              {{ chat.title }}
            </span>
          </div>
        </a>
        <i
          v-if="chat.id === currentChatId"
          class="select__item-active-icon iconoir-check"
        ></i>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'AssistantChatHistoryContext',
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
