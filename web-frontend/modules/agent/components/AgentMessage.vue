<template>
  <ChatMessage :own="own">
    <div v-if="own" class="chat-message__bubble">{{ message.content }}</div>
    <div
      v-else-if="shown.content || shown.replying"
      class="chat-message__bubble"
      aria-live="polite"
      :aria-busy="shown.replying"
    >
      <ChatTyping v-if="!shown.content" />
      <ChatLoading v-else :loading="shown.replying">
        <ChatMarkdown :content="shown.content" />
      </ChatLoading>
    </div>
    <div
      v-if="outcome.error"
      class="chat-message__bubble chat-message__bubble--error"
    >
      {{ $t(outcome.error) }}
    </div>
    <div v-if="outcome.note" class="chat-message__note">
      {{ $t(outcome.note) }}
    </div>
    <template v-if="shown.content && !shown.replying" #actions>
      <ChatCopyButton :text="shown.content" />
      <span class="chat-message__time">{{
        getHumanAgoLabel($t, message.created_on, now?.value)
      }}</span>
    </template>
  </ChatMessage>
</template>

<script setup>
import { computed } from 'vue'
import { useStore } from 'vuex'
import ChatCopyButton from '@baserow/modules/core/components/chat/ChatCopyButton'
import ChatLoading from '@baserow/modules/core/components/chat/ChatLoading'
import ChatMarkdown from '@baserow/modules/core/components/chat/ChatMarkdown'
import ChatMessage from '@baserow/modules/core/components/chat/ChatMessage'
import ChatTyping from '@baserow/modules/core/components/chat/ChatTyping'
import { isTerminalStatus } from '@baserow/modules/core/chatRuns/constants'
import { injectNow } from '@baserow/modules/core/composables/useNow'
import { getHumanAgoLabel } from '@baserow/modules/core/utils/date'
import { replyOutcome } from '@baserow/modules/agent/utils/replies'

const props = defineProps({ message: { type: Object, required: true } })

const store = useStore()
const now = injectNow()
const own = computed(() => props.message.role === 'user')
/** The saved message, or what its run wrote so far while it isn't saved. */
const shown = computed(() => {
  const { message } = props
  const follower =
    message.run_id && store.getters['chatRuns/getFollower'](message.run_id)
  // A follower that lost access can't say how the reply ended.
  if (
    !follower ||
    isTerminalStatus(message.status) ||
    (follower.finished && !isTerminalStatus(follower.view.status))
  ) {
    return { ...message, replying: false }
  }
  return {
    ...message,
    content: follower.view.text,
    status: follower.view.status,
    error_code: follower.view.errorCode,
    replying: !follower.finished,
  }
})
const outcome = computed(() => replyOutcome(shown.value))
</script>
