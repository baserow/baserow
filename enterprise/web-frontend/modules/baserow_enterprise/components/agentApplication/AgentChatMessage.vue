<template>
  <div
    class="agent-chat-message"
    :class="`agent-chat-message--${variant}`"
    :data-message-type="event.type"
  >
    <template v-if="variant === 'human'">
      <div class="agent-chat-message__content">{{ event.content }}</div>
      <div
        v-if="event.attachments && event.attachments.length > 0"
        class="agent-chat-message__attachments"
      >
        <div
          v-for="(attachment, index) in event.attachments"
          :key="index"
          class="agent-chat__attachment-chip"
        >
          <i
            class="agent-chat__attachment-chip-icon"
            :class="attachmentIcon(attachment)"
          ></i>
          <span class="agent-chat__attachment-chip-name">{{
            attachment.visible_name ||
            attachment.original_name ||
            attachment.name
          }}</span>
          <span
            v-if="attachment.size"
            class="agent-chat__attachment-chip-size"
            >{{ formatSize(attachment.size) }}</span
          >
        </div>
      </div>
    </template>
    <template v-else-if="variant === 'ai'">
      <!-- eslint-disable vue/no-v-html -->
      <div class="agent-chat-message__content" v-html="rendered"></div>
      <!-- eslint-enable vue/no-v-html -->
      <div v-if="!event.partial" class="agent-chat-message__actions">
        <a class="agent-chat-message__action" @click.prevent="copy">
          <i class="iconoir-copy"></i>
          {{ $t('agentChat.copy') }}
          <Copied ref="copied"></Copied>
        </a>
        <span v-if="event.created_on" class="agent-chat-message__time">
          {{ relativeTime }}
        </span>
      </div>
    </template>
    <template v-else-if="variant === 'cancelled'">
      {{ $t('agentChat.cancelled') }}
    </template>
    <template v-else>
      {{ event.content }}
    </template>
  </div>
</template>

<script>
import { defineComponent, computed, ref } from 'vue'
import moment from '@baserow/modules/core/moment'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import { renderMarkdown } from '@baserow_enterprise/utils/agentMarkdown'

const VARIANTS = {
  human: 'human',
  'ai/message': 'ai',
  'ai/error': 'error',
  'ai/cancelled': 'cancelled',
  system: 'system',
}

export default defineComponent({
  name: 'AgentChatMessage',
  props: {
    event: {
      type: Object,
      required: true,
    },
    attachmentIcon: {
      type: Function,
      required: false,
      default: () => 'iconoir-page',
    },
    formatSize: {
      type: Function,
      required: false,
      default: (size) => `${size}`,
    },
  },
  setup(props) {
    const copied = ref(null)
    const variant = computed(() => VARIANTS[props.event.type] || 'system')
    const rendered = computed(() => renderMarkdown(props.event.content))
    const relativeTime = computed(() =>
      moment(props.event.created_on).fromNow()
    )
    const copy = () => {
      copyToClipboard(props.event.content || '')
      copied.value?.show()
    }
    return { copied, variant, rendered, relativeTime, copy }
  },
})
</script>
