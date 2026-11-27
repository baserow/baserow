<template>
  <div class="assistant__input">
    <div
      v-if="!$slots.context || sending"
      class="assistant__input-status"
      :class="{ 'is-running': isRunning }"
    >
      <i class="iconoir-sparks assistant__input-status-icon"></i>
      <span v-if="!isRunning && !sending" class="assistant__status-message">
        {{ $t('assistantInputMessage.statusWaiting') }}
      </span>
      <span v-else class="assistant__status-message">
        {{ runningMessage || $t('assistant.statusThinking') }}
      </span>
    </div>
    <div class="assistant__input-section" :class="{ 'is-running': isRunning }">
      <div class="assistant__input-wrapper has-context">
        <slot name="context"
          ><AssistantUiContext :ui-context="uiContext"
        /></slot>

        <textarea
          ref="textarea"
          v-model="currentMessage"
          class="assistant__input-textarea"
          :placeholder="$t('assistantInputMessage.placeholder')"
          :rows="minRows"
          :maxlength="maxlength"
          @input="adjustHeight"
          @keydown.enter="handleEnter"
        ></textarea>

        <button
          class="assistant__send-button"
          :class="{
            'assistant__send-button--disabled': isSendDisabled,
            'assistant__send-button--is-running': isRunning,
            'assistant__send-button--is-cancelling': isCancelling,
          }"
          :disabled="isSendDisabled"
          :aria-label="
            isRunning
              ? $t('assistantInputMessage.stop')
              : $t('assistantInputMessage.send')
          "
          :title="
            isRunning
              ? $t('assistantInputMessage.stop')
              : $t('assistantInputMessage.send')
          "
          @click="handleButtonClick"
        >
          <i v-if="!isRunning" class="iconoir-arrow-up"></i>
          <i v-else class="iconoir-square assistant__send-button-icon-stop"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import AssistantUiContext from '@baserow_enterprise/components/assistant/AssistantUiContext'

export default {
  name: 'AssistantInputMessage',
  emits: ['cancel-message', 'send-message'],
  components: {
    AssistantUiContext,
  },
  props: {
    starter: { type: String, default: '' },
    sending: Boolean,
    sendDisabled: Boolean,
    maxlength: { type: Number, default: null },
    uiContext: {
      type: Object,
      default: () => ({}),
    },
    isRunning: {
      type: Boolean,
      default: false,
    },
    isCancelling: {
      type: Boolean,
      default: false,
    },
    runningMessage: {
      type: String,
      default: '',
    },
  },
  data() {
    return {
      currentMessage: this.starter ? this.starter + ' ' : '',
      minRows: 1,
      maxRows: 6,
    }
  },
  computed: {
    isSendDisabled() {
      return (
        (!this.isRunning &&
          (!this.currentMessage.trim() ||
            this.currentMessage.trim() === this.starter.trim())) ||
        this.isCancelling ||
        this.sending ||
        this.sendDisabled
      )
    },
  },
  mounted() {
    this.calculateLineHeight()
    this.adjustHeight()
    if (this.starter) {
      const end = this.currentMessage.length
      this.$refs.textarea.setSelectionRange(end, end)
    }
  },
  methods: {
    setCurrentMessage(message) {
      this.currentMessage = message

      this.$nextTick(() => {
        this.calculateLineHeight()
        this.adjustHeight()
        this.focus()
      })
    },
    focus() {
      this.$refs.textarea.focus()
    },
    handleEnter(event) {
      // If shift key is pressed, allow the default behavior (new line)
      if (event.isComposing || event.keyCode === 229) return
      if (!event.shiftKey) {
        event.preventDefault()
        if (!this.isRunning) {
          this.sendMessage()
        }
      }
    },
    handleButtonClick() {
      if (this.isRunning) {
        this.cancelMessage()
      } else {
        this.sendMessage()
      }
    },
    sendMessage() {
      const message = this.currentMessage.trim()
      if (this.isSendDisabled || this.isRunning) return

      this.$emit('send-message', message)

      this.clear()
    },
    cancelMessage() {
      if (!this.isRunning || this.isCancelling) return
      this.$emit('cancel-message')
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
