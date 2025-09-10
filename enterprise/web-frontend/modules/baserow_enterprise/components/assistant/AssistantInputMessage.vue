<template>
  <div class="assistant__input">
    <div class="assistant__input-status" :class="{ 'is-running': running }">
      <i class="iconoir-sparks assistant__input-status-icon"></i>
      <span v-if="!running" class="assistant__status-waiting">
        {{ $t('assistantInputMessage.statusWaiting') }}
      </span>
      <span v-else class="assistant__status-running">
        {{ $t('assistantInputMessage.statusRunning') }}
      </span>
    </div>
    <div class="assistant__input-section" :class="{ 'is-running': running }">
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
          :placeholder="$t('assistantInputMessage.placeholder')"
          :auto-expandable="true"
          :min-rows="1"
          :max-rows="6"
          @keydown.enter="handleEnter"
        />
        <button
          class="assistant__send-button"
          :class="{
            'assistant__send-button--disabled':
              !currentMessage.trim() || running,
            'assistant__send-button--is-running': running,
          }"
          :disabled="!currentMessage.trim() || running"
          :title="$t('assistantInputMessage.send')"
          @click="sendMessage"
        >
          <i v-if="!running" class="iconoir-arrow-up"></i>
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
    running: {
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
      if (!message || this.running) return

      this.$emit('send-message', message)
      this.currentMessage = ''
    },
  },
}
</script>
