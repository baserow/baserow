<template>
  <RadioGroup
    :model-value="currentValue"
    :options="options"
    type="button"
    @input="input"
  />
</template>

<script>
import { WIDTHS_NEW } from '@baserow/modules/builder/enums'

export default {
  name: 'WidthSelector',
  props: {
    /**
     * Vue 3 v-model value.
     */
    modelValue: {
      type: String,
      default: undefined,
    },

    /**
     * Vue 2 v-model value.
     */
    value: {
      type: String,
      required: false,
      default: WIDTHS_NEW.AUTO,
    },
  },
  emits: ['input', 'update:modelValue'],
  computed: {
    // Prefer Vue 3 modelValue when defined.
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
    options() {
      return [
        { value: WIDTHS_NEW.AUTO, label: this.$t('widthSelector.widthAuto') },
        { value: WIDTHS_NEW.FULL, label: this.$t('widthSelector.widthFull') },
      ]
    },
  },
  methods: {
    input(value) {
      // Vue 3 emit
      this.$emit('update:modelValue', value)
      // Vue 2 emit
      this.$emit('input', value)
    },
  },
}
</script>
