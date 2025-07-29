<template>
  <div class="ai-assistant__messages-list">
    <div
      v-for="message in messages"
      :key="message.id"
      class="ai-assistant__message"
      :class="{
        'ai-assistant__message--user': message.role === 'user',
        'ai-assistant__message--assistant': message.role === 'assistant',
      }"
    >
      <div class="ai-assistant__message-content">
        <div class="ai-assistant__message-bubble">
          <div
            v-if="message.role === 'assistant' && message.loading"
            class="ai-assistant__typing"
          >
            <span></span>
            <span></span>
            <span></span>
          </div>
          <!-- eslint-disable vue/no-v-html -->
          <div
            v-else
            @click="interceptLinkClick"
            class="ai-assistant__message-text"
            v-html="formatMessage(message.content)"
          ></div>
        </div>

        <!-- Confirmation buttons -->
        <div
          v-if="message.requiresConfirmation && message.actionId"
          class="ai-assistant__confirmation"
        >
          <button
            class="ai-assistant__confirmation-button ai-assistant__confirmation-button--confirm"
            @click="$emit('confirm-action', message.actionId)"
          >
            <i class="iconoir-check"></i>
            {{ $t('aiAssistantPanel.confirm', 'Confirm') }}
          </button>
          <button
            class="ai-assistant__confirmation-button ai-assistant__confirmation-button--cancel"
            @click="$emit('cancel-action', message.actionId)"
          >
            <i class="iconoir-cancel"></i>
            {{ $t('aiAssistantPanel.cancel', 'Cancel') }}
          </button>
        </div>

        <!-- Footer with actions -->
        <div class="ai-assistant__message-footer">
          <div
            v-if="
              message.role === 'assistant' &&
              !message.loading &&
              !message.requiresConfirmation
            "
            class="ai-assistant__message-actions"
          >
            <button
              class="ai-assistant__message-action"
              :title="$t('aiAssistantPanel.like', 'Like')"
              @click="$emit('like-message', message)"
            >
              <i class="iconoir-thumbs-up"></i>
            </button>
            <button
              class="ai-assistant__message-action"
              :title="$t('aiAssistantPanel.dislike', 'Dislike')"
              @click="$emit('dislike-message', message)"
            >
              <i class="iconoir-thumbs-down"></i>
            </button>
            <button
              class="ai-assistant__message-action"
              :title="$t('aiAssistantPanel.copy', 'Copy')"
              @click="$emit('copy-message', message)"
            >
              <i class="iconoir-copy"></i>
            </button>
            <button
              v-if="canUndo(message)"
              class="ai-assistant__message-action ai-assistant__message-action--undo"
              :title="$t('aiAssistantPanel.undo')"
              @click="$emit('undo')"
            >
              <i class="iconoir-undo"></i>
              Undo
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import MarkdownIt from 'markdown-it'

// Initialize markdown parser with safe settings
const md = new MarkdownIt({
  html: false, // Disable HTML tags for security
  linkify: true, // Auto-convert URLs to links
  typographer: true, // Enable smart quotes and other typography
  breaks: true, // Convert line breaks to <br>
})

export default {
  name: 'AiAssistantMessageList',
  props: {
    messages: {
      type: Array,
      default: () => [],
    },
  },
  watch: {
    messages: {
      handler(newMessages) {
        const lastMsg = newMessages.at(-1)
        const data = lastMsg.action
        if (data) {
          switch (data.type) {
            case 'table_navigation':
              this.$router.push(data.url)
              // this.$emit('table-navigation-done', data.url)
              break
          }
        }

        this.$nextTick(() => {
          const container = this.$el
          container.scrollTop = container.scrollHeight
        })
      },
    },
  },
  methods: {
    canUndo(message) {
      return this.$store.getters['aiAssistant/canUndo'](message)
    },
    formatMessage(content) {
      // Parse markdown content and return safe HTML
      if (!content) return ''

      // Render markdown to HTML
      const html = md.render(content)

      // Return the sanitized HTML
      return html
    },
    interceptLinkClick(e) {
      // Check if clicked element is a link
      const target = e.target.closest('a')
      if (!target) return

      const href = target.getAttribute('href')
      if (!href) return

      // Determine if it's an internal link
      if (this.isInternalLink(href)) {
        e.preventDefault()

        // Use Nuxt router for navigation
        this.$router.push(href)
      }
      // External links will work normally
    },

    isInternalLink(href) {
      // Check if the link is internal
      if (!href) return false

      // Relative links
      if (href.startsWith('/')) return true

      // Same origin links
      const url = new URL(href, window.location.origin)
      return url.origin === window.location.origin
    },
  },
}
</script>
