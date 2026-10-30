<template>
  <ChatMessage :own="own" :class="{ 'chat-message--steps': groups.length }">
    <ChatStepGroup v-for="group in groups" :key="group.id" v-bind="group" />
    <div v-if="own" class="chat-message__bubble">{{ message.content }}</div>
    <div
      v-else-if="shown.content || (shown.replying && !toolRunning)"
      class="chat-message__bubble"
      aria-live="polite"
      :aria-busy="shown.replying"
    >
      <ChatTyping v-if="!shown.content" />
      <ChatMarkdown v-else :content="shown.content" />
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
      <ChatMessageFooter
        :text="shown.content"
        :timestamp="message.created_on"
      />
    </template>
  </ChatMessage>
</template>

<script setup>
import { MESSAGE_ROLE } from '@baserow/modules/agent/constants'
import { computed } from 'vue'
import { useStore } from 'vuex'
import { useI18n } from 'vue-i18n'
import { useNuxtApp } from '#app'
import ChatMessageFooter from '@baserow/modules/core/components/chat/ChatMessageFooter'
import ChatMarkdown from '@baserow/modules/core/components/chat/ChatMarkdown'
import ChatMessage from '@baserow/modules/core/components/chat/ChatMessage'
import ChatTyping from '@baserow/modules/core/components/chat/ChatTyping'
import ChatStepGroup from '@baserow/modules/core/components/chat/ChatStepGroup'
import { groupToolSteps } from '@baserow/modules/core/toolPresentationTypes'
import { isTerminalStatus } from '@baserow/modules/core/chatRuns/constants'
import { replyOutcome } from '@baserow/modules/agent/utils/replies'

const props = defineProps({ message: { type: Object, required: true } })

const store = useStore()
const { $registry } = useNuxtApp()
const { t } = useI18n()
const own = computed(() => props.message.role === MESSAGE_ROLE.USER)
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
    steps: follower.view.steps,
    replying: !follower.finished,
  }
})
const groups = computed(() =>
  own.value ? [] : groupToolSteps(shown.value.steps, $registry, t)
)
const toolRunning = computed(() =>
  shown.value.steps?.some((step) => step.status === 'running')
)
const outcome = computed(() => replyOutcome(shown.value))
</script>
