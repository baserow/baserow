<template>
  <div class="assistant__messages-list">
    <div
      v-for="(message, index) in messages"
      :key="message.id"
      class="assistant__message"
      :class="{
        'assistant__message--human': message.role === 'human',
        'assistant__message--ai': message.role === 'ai',
        'assistant__message--error': message.error,
        'assistant__message--cancelled': message.cancelled,
        'assistant__message--reasoning': message.reasoning,
      }"
    >
      <div class="assistant__message-content">
        <div class="assistant__message-bubble">
          <ChatTyping v-if="waitingForAssistantResponse(message)" />
          <template v-else>
            <ChatLoading :loading="message.reasoning">
              <!-- eslint-disable vue/no-v-html -->
              <div
                class="assistant__message-text"
                :class="{
                  'assistant__message-text--collapsed':
                    message.reasoning && !expandedReasoning[message.id],
                }"
                @click="interceptLinkClick"
                v-html="formatMessage(message.content)"
              ></div>
            </ChatLoading>
            <button
              v-if="message.reasoning"
              class="assistant__reasoning-toggle"
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

        <AssistantMessageActions :message="message" />
        <div
          v-if="message.can_submit_feedback && isLastMessage(index)"
          class="assistant__disclaimer"
        >
          {{ $t('assistantMessageList.disclaimer') }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import MarkdownIt from 'markdown-it'
import ChatLoading from '@baserow/modules/core/components/chat/ChatLoading'
import ChatTyping from '@baserow/modules/core/components/chat/ChatTyping'
import AssistantMessageSources from './AssistantMessageSources'
import AssistantMessageActions from './AssistantMessageActions'

// Initialize markdown parser with safe settings
const md = new MarkdownIt({
  html: false, // Disable HTML tags for security
  linkify: true, // Auto-convert URLs to links
  typographer: true, // Enable smart quotes and other typography
  breaks: false, // Convert line breaks to <br>
})

export default {
  name: 'AssistantMessageList',
  components: {
    ChatLoading,
    ChatTyping,
    AssistantMessageSources,
    AssistantMessageActions,
  },
  props: {
    messages: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      expandedSources: {},
      expandedReasoning: {},
    }
  },
  methods: {
    waitingForAssistantResponse(message) {
      return message.role === 'ai' && message.loading && !message.content
    },
    formatMessage(content) {
      if (!content) return ''

      const html = md.render(content)
      return html
    },
    /**
     * Intercepts link clicks to handle internal navigation.
     * If the link is internal, it uses the router to navigate.
     * If the link is external, it opens in a new tab to show the content.
     */
    interceptLinkClick(event) {
      const target = event.target.closest('a')
      if (!target) return

      const href = target.getAttribute('href')
      if (!href) return

      if (this.isInternalLink(href)) {
        event.preventDefault()
        this.$router.push(href)
      } else {
        // Open external links in a new tab
        window.open(href, '_blank', 'noopener,noreferrer')
        event.preventDefault()
      }
    },

    isInternalLink(href) {
      if (!href) return false

      // Relative links
      if (href.startsWith('/')) return true

      // Same origin links
      const url = new URL(href, window.location.origin)
      return url.origin === window.location.origin
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
