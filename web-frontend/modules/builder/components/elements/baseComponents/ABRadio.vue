<template>
  <div class="ab-radio" @click="toggle">
    <input
      type="radio"
      :checked="modelValue"
      :required="required"
      class="ab-radio__input"
      :disabled="disabled"
      :class="{
        'ab-radio--error': error,
        'ab-radio--readonly': readOnly,
      }"
      :aria-disabled="disabled"
    />
    <label v-if="hasSlot" class="ab-radio__label">
      <slot></slot>
    </label>
  </div>
</template>

<script>
export default {
  name: 'ABRadio',
  props: {
    /**
     * The state of the radio.
     */
    modelValue: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the radio is disabled.
     */
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the radio is required.
     */
    required: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the radio is in error state.
     */
    error: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the radio is readonly.
     */
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['update:modelValue'],
  computed: {
    hasSlot() {
      return !!this.$slots.default
    },
  },
  methods: {
    toggle() {
      if (this.disabled || this.readOnly) return
      this.$emit('update:modelValue', !this.value)
    },
  },
}
</script>
