<template>
  <div class="ab-toast" @mouseenter="pauseTimer" @mouseleave="resumeTimer">
    <div v-if="type">
      <div class="ab-toast__icon" :class="`ab-toast__icon--${type}`">
        <i v-if="icon" :class="icon"></i>
      </div>
    </div>
    <div class="ab-toast__content">
      <div v-if="hasTitleSlot" class="ab-toast__title">
        <slot name="title" />
      </div>
      <div v-if="hasContentSlot" class="ab-toast__message"><slot /></div>
      <div v-if="hasActionsSlot" class="ab-toast__actions">
        <slot name="actions" />
      </div>
    </div>
    <button v-if="closeButton" class="ab-toast__close" @click="$emit('close')">
      <i class="iconoir-cancel"></i>
    </button>
  </div>
</template>
<script>
export default {
  name: 'BuilderToast',
  props: {
    /**
     * The type of toast to display
     */
    type: {
      type: String,
      default: 'info-primary',
      validator: function (value) {
        return [
          'info-neutral',
          'info-primary',
          'warning',
          'error',
          'success',
        ].includes(value)
      },
    },
    /**
     * The icon to display in the toast.
     */
    icon: {
      type: String,
      default: null,
    },
    /**
     * Whether to display a close button or not.
     */
    closeButton: {
      required: false,
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      timer: null,
      remainingTime: 5000,
      startTime: null,
    }
  },
  computed: {
    hasTitleSlot() {
      return !!this.$slots.title
    },
    hasActionsSlot() {
      return !!this.$slots.actions
    },
    hasContentSlot() {
      return !!this.$slots.default
    },
  },
  mounted() {
    this.startTimer()
  },
  beforeDestroy() {
    this.clearTimer()
  },
  methods: {
    startTimer() {
      this.startTime = Date.now()
      this.timer = setTimeout(() => {
        this.close()
      }, this.remainingTime)
    },
    clearTimer() {
      if (this.timer) {
        clearTimeout(this.timer)
        this.timer = null
      }
    },
    pauseTimer() {
      if (this.timer) {
        this.clearTimer()
        this.remainingTime -= Date.now() - this.startTime
      }
    },
    resumeTimer() {
      if (this.remainingTime > 0) {
        this.startTimer()
      }
    },
    close() {
      this.$emit('close')
    },
  },
}
</script>
