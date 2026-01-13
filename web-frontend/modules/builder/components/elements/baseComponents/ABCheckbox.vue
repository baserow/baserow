<template>
  <div class="ab-checkbox" @click="toggle">
    <input
      type="checkbox"
      :checked="modelValue"
      :required="required"
      class="ab-checkbox__input"
      :disabled="disabled"
      :class="{
        'ab-checkbox--error': error,
        'ab-checkbox--readonly': readOnly,
      }"
      :aria-disabled="disabled"
    />
    <label v-if="hasSlot" class="ab-checkbox__label">
      <slot></slot>
    </label>
  </div>
</template>

<script>
export default {
  name: 'ABCheckbox',
  props: {
    /**
     * The state of the checkbox.
     */
    modelValue: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the checkbox is disabled.
     */
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the checkbox is required.
     */
    required: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the checkbox is in error state.
     */
    error: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the checkbox is readonly.
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
      this.$emit('update:modelValue', !this.modelValue)
    },
  },
}
</script>
