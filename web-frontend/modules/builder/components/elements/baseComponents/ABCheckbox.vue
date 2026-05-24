<template>
  <div class="ab-checkbox">
    <input
      :id="inputId"
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
      @change="onChange"
    />
    <label v-if="hasSlot" :for="inputId" class="ab-checkbox__label">
      <slot></slot>
    </label>
  </div>
</template>

<script>
import { useId } from 'vue'

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
  setup() {
    const uniqId = useId()

    return { uniqId }
  },
  computed: {
    inputId() {
      return `ab-checkbox-${this.uniqId}`
    },
    hasSlot() {
      return !!this.$slots.default
    },
  },
  methods: {
    onChange(event) {
      if (this.disabled || this.readOnly) return
      this.$emit('update:modelValue', event.target.checked)
    },
  },
}
</script>
