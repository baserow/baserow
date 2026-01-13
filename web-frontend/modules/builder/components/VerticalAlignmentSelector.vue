<template>
  <RadioGroup
    :model-value="currentValue"
    :options="alignmentValues"
    type="button"
    @input="input"
  />
</template>

<script>
import { VERTICAL_ALIGNMENTS } from '@baserow/modules/builder/enums'

export default {
  name: 'VerticalAlignmentSelector',
  props: {
    /**
     * Vue 3 v-model binding.
     */
    modelValue: {
      type: String,
      default: undefined,
    },
    /**
     * Vue 2 v-model binding.
     */
    value: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['input', 'update:modelValue'],
  computed: {
    // Prefer Vue 3 modelValue when provided, otherwise fall back to Vue 2 value.
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
    alignmentValues() {
      return [
        {
          title: this.$t('verticalAlignmentSelector.alignmentTop'),
          value: VERTICAL_ALIGNMENTS.TOP,
          icon: 'iconoir-align-top-box',
        },
        {
          title: this.$t('verticalAlignmentSelector.alignmentCenter'),
          value: VERTICAL_ALIGNMENTS.CENTER,
          icon: 'iconoir-center-align',
        },
        {
          title: this.$t('verticalAlignmentSelector.alignmentBottom'),
          value: VERTICAL_ALIGNMENTS.BOTTOM,
          icon: 'iconoir-align-bottom-box',
        },
      ]
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
