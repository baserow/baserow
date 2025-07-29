<template>
  <div class="ai-assistant__bottom-input-section">
    <!-- Single input bubble with context inside -->
    <div
      class="ai-assistant__input-wrapper"
      :class="{ 'has-context': hasContext }"
    >
      <!-- Context badge in top-left corner -->
      <div v-if="hasContext" class="ai-assistant__context-badge">
        <i class="ai-assistant__context-icon iconoir-at-sign"></i>
        <span class="ai-assistant__context-text">{{ contextDisplay }}</span>
      </div>

      <FormTextarea
        ref="messageInput"
        v-model="currentMessage"
        :placeholder="placeholder"
        :auto-expandable="true"
        :min-rows="2"
        :max-rows="6"
        @keydown.enter="handleEnter"
      />
      <button
        class="ai-assistant__send-button"
        :class="{
          'ai-assistant__send-button--disabled':
            !currentMessage.trim() || loading,
        }"
        :disabled="!currentMessage.trim() || loading"
        :title="$t('aiAssistantPanel.send', 'Send message')"
        @click="sendMessage"
      >
        <i v-if="!loading" class="iconoir-send"></i>
        <i
          v-else
          class="iconoir-system-restart ai-assistant__send-button--loading"
        ></i>
      </button>
    </div>
  </div>
</template>

<script>
import FormTextarea from '@baserow/modules/core/components/FormTextarea'

export default {
  name: 'AiAssistantInputSection',
  components: {
    FormTextarea,
  },
  props: {
    hasContext: {
      type: Boolean,
      default: false,
    },
    contextDisplay: {
      type: String,
      default: '',
    },
    placeholder: {
      type: String,
      default: 'Type your message...',
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['send-message'],
  data() {
    return {
      currentMessage: '',
    }
  },
  methods: {
    handleEnter(event) {
      if (!event.shiftKey) {
        event.preventDefault()
        this.sendMessage()
      }
      // If shift key is pressed, allow the default behavior (new line)
    },
    sendMessage() {
      const message = this.currentMessage.trim()
      if (!message || this.loading) return

      this.$emit('send-message', message)
      this.currentMessage = ''
    },
  },
}
</script>
