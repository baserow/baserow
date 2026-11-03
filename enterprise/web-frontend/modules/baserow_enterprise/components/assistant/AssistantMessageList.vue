<template>
  <div class="assistant__messages-list">
    <template
      v-for="(message, index) in messages"
      :key="message._uuid || message.id"
    >
      <ChatMessage :own="message.role === 'human'">
        <div v-if="message.cancelled" class="chat-message__note">
          {{ message.content }}
        </div>
        <div
          v-else
          class="chat-message__bubble"
          :class="{ 'chat-message__bubble--error': message.error }"
          :aria-live="message.role === 'ai' ? 'polite' : undefined"
          :aria-busy="isBusy(message, index)"
        >
          <template v-if="message.role === 'human'">{{
            message.content
          }}</template>
          <ChatTyping v-else-if="message.loading && !message.content" />
          <template v-else>
            <ChatMarkdown
              :id="
                message.reasoning
                  ? `assistant-reasoning-${message.id}`
                  : undefined
              "
              :content="message.content || ''"
              :class="{
                'assistant__reasoning--collapsed':
                  message.reasoning && !expandedReasoning[message.id],
              }"
            />
            <button
              v-if="message.reasoning"
              type="button"
              class="assistant__reasoning-toggle"
              :aria-controls="`assistant-reasoning-${message.id}`"
              :aria-expanded="Boolean(expandedReasoning[message.id])"
              :aria-label="
                $t(
                  expandedReasoning[message.id]
                    ? 'assistantMessageList.collapseReasoning'
                    : 'assistantMessageList.expandReasoning'
                )
              "
              @click="toggleReasoning(message.id)"
            >
              <i
                class="iconoir-nav-arrow-down assistant__reasoning-chevron"
                :class="{
                  'assistant__reasoning-chevron--expanded':
                    expandedReasoning[message.id],
                }"
              ></i>
            </button>
            <AssistantMessageSources
              v-if="message.role === 'ai'"
              :sources="message.sources"
              :expanded="expandedSources[message.id] || false"
              @toggle="toggleSources(message.id)"
            />
          </template>
        </div>
        <template
          v-if="
            message.content && !message.reasoning && !isBusy(message, index)
          "
          #actions
        >
          <ChatMessageFooter
            :text="message.content"
            :timestamp="message.timestamp"
            @error="copyFailed"
          >
            <AssistantMessageActions
              v-if="message.can_submit_feedback"
              :message="message"
            />
          </ChatMessageFooter>
        </template>
      </ChatMessage>
      <div
        v-if="message.can_submit_feedback && isLastMessage(index)"
        class="assistant__disclaimer"
      >
        {{ $t('assistantMessageList.disclaimer') }}
      </div>
    </template>
  </div>
</template>

<script>
import ChatMessage from '@baserow/modules/core/components/chat/ChatMessage'
import ChatMarkdown from '@baserow/modules/core/components/chat/ChatMarkdown'
import ChatTyping from '@baserow/modules/core/components/chat/ChatTyping'
import ChatMessageFooter from '@baserow/modules/core/components/chat/ChatMessageFooter'
import AssistantMessageSources from './AssistantMessageSources'
import AssistantMessageActions from './AssistantMessageActions'

export default {
  name: 'AssistantMessageList',
  components: {
    ChatMessage,
    ChatMarkdown,
    ChatTyping,
    ChatMessageFooter,
    AssistantMessageSources,
    AssistantMessageActions,
  },
  props: {
    messages: { type: Array, default: () => [] },
    running: { type: Boolean, default: false },
  },
  data() {
    return {
      expandedSources: {},
      expandedReasoning: {},
    }
  },
  methods: {
    isBusy(message, index) {
      return (
        message.role === 'ai' &&
        !message.error &&
        !message.cancelled &&
        (message.loading || (this.running && this.isLastMessage(index)))
      )
    },
    copyFailed() {
      this.$store.dispatch('toast/error', {
        title: this.$t('assistantMessageActions.copyFailed'),
      })
    },
    toggleSources(messageId) {
      this.expandedSources[messageId] = !this.expandedSources[messageId]
    },
    toggleReasoning(messageId) {
      this.expandedReasoning[messageId] = !this.expandedReasoning[messageId]
    },
    isLastMessage(index) {
      return index === this.messages.length - 1
    },
  },
}
</script>
