<template>
  <div class="ai-assistant__input">
    <div class="ai-assistant__input-status" :class="{ 'is-running': loading }">
      <i class="iconoir-sparks ai-assistant__input-status-icon"></i>
      <span v-if="!loading" class="ai-assistant__status-waiting">
        {{ $t('aiAssistantInputMessage.statusWaiting') }}
      </span>
      <span v-else class="ai-assistant__status-running">
        {{ $t('aiAssistantInputMessage.statusRunning') }}
      </span>
    </div>
    <div class="ai-assistant__input-section" :class="{ 'is-running': loading }">
      <div
        class="ai-assistant__input-wrapper"
        :class="{ 'has-context': contextDisplay }"
      >
        <div v-if="contextDisplay" class="ai-assistant__context-badge">
          <span class="ai-assistant__context-text">{{ contextDisplay }}</span>
        </div>

        <FormTextarea
          ref="messageInput"
          v-model="currentMessage"
          :placeholder="$t('aiAssistantInputMessage.placeholder')"
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
            'ai-assistant__send-button--is-running': loading,
          }"
          :disabled="!currentMessage.trim() || loading"
          :title="$t('aiAssistantInputMessage.send')"
          @click="sendMessage"
        >
          <i v-if="!loading" class="iconoir-arrow-up"></i>
          <i v-else class="iconoir-system-restart"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import FormTextarea from '@baserow/modules/core/components/FormTextarea'

export default {
  name: 'AiAssistantInputMessage',
  components: {
    FormTextarea,
  },
  props: {
    contextDisplay: {
      type: String,
      default: '',
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      currentMessage: '',
    }
  },
  methods: {
    handleEnter(event) {
      // If shift key is pressed, allow the default behavior (new line)
      if (!event.shiftKey) {
        event.preventDefault()
        this.sendMessage()
      }
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
