<template>
  <div class="chat-message__footer">
    <ChatCopyButton :text="text" @error="$emit('error', $event)" />
    <slot />
    <time v-if="timeLabel" class="chat-message__time" :datetime="timestamp">
      {{ timeLabel }}
    </time>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ChatCopyButton from '@baserow/modules/core/components/chat/ChatCopyButton'
import moment from '@baserow/modules/core/moment'
import { injectNow } from '@baserow/modules/core/composables/useNow'
import { getHumanAgoLabel } from '@baserow/modules/core/utils/date'

const props = defineProps({
  text: { type: String, required: true },
  timestamp: { type: String, default: null },
})
defineEmits(['error'])

const { t } = useI18n()
const now = injectNow()
const timeLabel = computed(() => {
  if (
    !props.timestamp ||
    !moment(props.timestamp, moment.ISO_8601, true).isValid()
  )
    return ''
  return getHumanAgoLabel(t, props.timestamp, now?.value)
})
</script>
