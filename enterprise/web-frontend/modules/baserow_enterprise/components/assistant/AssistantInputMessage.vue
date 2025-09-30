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

        <textarea
          ref="textarea"
          v-model="currentMessage"
          class="assistant__input-textarea"
          :placeholder="$t('assistantInputMessage.placeholder')"
          :rows="minRows"
          @input="adjustHeight"
          @keydown.enter="handleEnter"
        ></textarea>

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
export default {
  name: 'AssistantInputMessage',
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
      minRows: 1,
      maxRows: 6,
    }
  },
  mounted() {
    this.calculateLineHeight()
    this.adjustHeight()
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

      this.clear()
    },
    calculateLineHeight() {
      const textarea = this.$refs.textarea
      const computedStyle = window.getComputedStyle(textarea)
      this.lineHeight = parseInt(computedStyle.lineHeight) || 24
    },
    adjustHeight() {
      const textarea = this.$refs.textarea
      if (!textarea) return

      // Reset height to auto to get the correct scrollHeight
      textarea.style.height = 'auto'

      // Calculate the number of lines
      const scrollHeight = textarea.scrollHeight
      const minHeight = this.lineHeight * this.minRows
      const maxHeight = this.lineHeight * this.maxRows

      // Set the height based on content, within min/max bounds
      const newHeight = Math.max(minHeight, Math.min(scrollHeight, maxHeight))

      textarea.style.height = newHeight + 'px'
      textarea.style.overflowY = scrollHeight > maxHeight ? 'auto' : 'hidden'
    },
    clear() {
      this.currentMessage = ''
      this.$nextTick(this.adjustHeight)
    },
  },
}
</script>
