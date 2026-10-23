<template>
  <div
    class="chat-message"
    :class="{
      'chat-message--own': own,
      'chat-message--first': first,
      'chat-message--last': last,
    }"
  >
    <div v-if="!own" class="chat-message__gutter">
      <span
        v-if="last && initial"
        class="chat-message__avatar"
        :class="`chat-message__avatar--${authorType}`"
        aria-hidden="true"
        >{{ initial }}</span
      >
    </div>
    <div class="chat-message__body">
      <div v-if="!own && first && author" class="chat-message__author">
        {{ author }}
        <span v-if="status" :key="status" class="chat-shimmer">{{
          status
        }}</span>
      </div>
      <slot />
      <div v-if="$slots.actions" class="chat-message__actions">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** The viewer's own message, shown on the right without its author. */
  own: { type: Boolean, default: false },
  /** Who wrote the message, named above the first message of their run. */
  author: { type: String, default: '' },
  /** Agents get a square avatar, people a round one. */
  authorType: {
    type: String,
    default: 'agent',
    validator: (value) => ['agent', 'person'].includes(value),
  },
  /** Whether it starts a run of messages by the same author. */
  first: { type: Boolean, default: true },
  /** Whether it ends a run of messages by the same author. */
  last: { type: Boolean, default: true },
  /** What the author is doing before anything is written, like "Thinking…". */
  status: { type: String, default: '' },
})

const initial = computed(
  () => Array.from(props.author.trim())[0]?.toUpperCase() || ''
)
</script>
