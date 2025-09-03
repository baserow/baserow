<template>
  <div ref="list" class="ai-assistant__messages-list">
    <div
      v-for="message in messages"
      :key="message.id"
      class="ai-assistant__message"
      :class="{
        'ai-assistant__message--human': message.role === 'human',
        'ai-assistant__message--ai': message.role === 'ai',
      }"
    >
      <div class="ai-assistant__message-content">
        <div class="ai-assistant__message-bubble">
          <div
            v-if="message.role === 'ai' && message.loading && !message.content"
            class="ai-assistant__typing"
          >
            <span></span>
            <span></span>
            <span></span>
          </div>
          <!-- eslint-disable vue/no-v-html -->
          <div
            v-else
            class="ai-assistant__message-text"
            @click="interceptLinkClick"
            v-html="formatMessage(message.content)"
          ></div>
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
  data() {
    return {
      observer: null,
      mutationTimer: null,
    }
  },
  mounted() {
    this.observer = new MutationObserver(() => {
      clearTimeout(this.mutationTimer)
      this.mutationTimer = setTimeout(() => {
        this.$emit('scroll-to-bottom')
      }, 50)
    })

    this.observer.observe(this.$refs.list, {
      childList: true, // nodes added/removed
      subtree: true, // observe all descendants
      characterData: true, // text changes
    })
  },
  beforeDestroy() {
    this.observer.disconnect()
    this.observer = null
    clearTimeout(this._mutationTimer)
    this.mutationTimer = null
  },
  methods: {
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
  },
}
</script>
