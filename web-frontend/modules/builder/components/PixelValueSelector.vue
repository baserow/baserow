<template>
  <FormInput
    :value="currentValue"
    :default-value-when-empty="defaultValueWhenEmpty"
    type="number"
    remove-number-input-controls
    :to-value="(value) => (value ? parseInt(value) : null)"
    :style="{
      width: '100px',
    }"
    @input="input"
    @blur="$emit('blur')"
  >
    <template #suffix>px</template>
  </FormInput>
</template>

<script>
export default {
  name: 'PixelValueSelector',
  emits: ['input', 'update:modelValue', 'blur'],
  props: {
    /**
     * The model value in Vue 3 style.
     */
    modelValue: {
      type: Number,
      default: undefined,
    },
    /**
     * The model value in Vue 2 style.
     */
    value: {
      type: Number,
      required: false,
      default: null,
    },
    defaultValueWhenEmpty: {
      type: Number,
      required: false,
      default: null,
    },
  },
  computed: {
    // Prefer Vue 3 modelValue if provided, else fall back to Vue 2 value
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
  },
  methods: {
    input(value) {
      // Vue 3 style
      this.$emit('update:modelValue', value)
      // Vue 2 style
      this.$emit('input', value)
    },
  },
}
</script>
