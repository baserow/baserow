<template>
  <div class="toast">
    <div v-if="type">
      <div class="toast__icon" :class="`toast__icon--${type}`">
        <i v-if="loading" class="toast__loading"></i>
        <i v-else-if="icon" :class="icon"></i>
      </div>
    </div>

    <div class="toast__content">
      <div v-if="hasTitleSlot" class="toast__title">
        <slot name="title" />
      </div>
      <p v-if="hasContentSlot" class="toast__message"><slot /></p>

      <div v-if="hasActionsSlot" class="toast__actions">
        <slot name="actions" />
      </div>
    </div>

    <button v-if="closeButton" class="toast__close" @click="$emit('close')">
      <i class="iconoir-cancel"></i>
    </button>
  </div>
</template>

<script>
export default {
  name: 'Toast',
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
     * Whether to display a loading spinner or not.
     */
    loading: {
      required: false,
      type: Boolean,
      default: false,
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
  emits: ['close'],
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
    setTimeout(() => {
      this.close()
    }, 5000)
  },
  methods: {
    close() {
      this.$emit('close')
    },
  },
}
</script>
