<template>
  <div class="assistant__input">
    <div class="assistant__input-status" :class="{ 'is-running': loading }">
      <i class="iconoir-sparks assistant__input-status-icon"></i>
      <span v-if="!loading" class="assistant__status-waiting">
        {{ $t('aiAssistantInputMessage.statusWaiting') }}
      </span>
      <span v-else class="assistant__status-running">
        {{ $t('aiAssistantInputMessage.statusRunning') }}
      </span>
    </div>
    <div class="assistant__input-section" :class="{ 'is-running': loading }">
      <div
        class="assistant__input-wrapper"
        :class="{ 'has-context': contextDisplay }"
      >
        <div v-if="contextDisplay" class="assistant__context-badge">
          <span class="assistant__context-text">{{ contextDisplay }}</span>
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
          class="assistant__send-button"
          :class="{
            'assistant__send-button--disabled':
              !currentMessage.trim() || loading,
            'assistant__send-button--is-running': loading,
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
  name: 'AssistantInputMessage',
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
