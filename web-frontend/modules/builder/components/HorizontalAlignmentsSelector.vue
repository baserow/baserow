<template>
  <RadioGroup
    :model-value="currentValue"
    :options="alignmentValues"
    type="button"
    @input="input"
  />
</template>

<script>
import { HORIZONTAL_ALIGNMENTS } from '@baserow/modules/builder/enums'

export default {
  name: 'HorizontalAlignmentsSelector',
  props: {
    /**
     * The model value of the component in Vue 3 style.
     */
    modelValue: {
      type: String,
      default: undefined,
    },

    /**
     * The model value of the component in Vue 2 style.
     */
    value: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['input', 'update:modelValue'],
  computed: {
    // Prefer Vue 3 modelValue if provided, else fall back to Vue 2 value
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },

    alignmentValues() {
      return [
        {
          title: this.$t('horizontalAlignmentSelector.alignmentLeft'),
          value: HORIZONTAL_ALIGNMENTS.LEFT,
          icon: 'iconoir-align-left',
        },
        {
          title: this.$t('horizontalAlignmentSelector.alignmentCenter'),
          value: HORIZONTAL_ALIGNMENTS.CENTER,
          icon: 'iconoir-align-center',
        },
        {
          title: this.$t('horizontalAlignmentSelector.alignmentRight'),
          value: HORIZONTAL_ALIGNMENTS.RIGHT,
          icon: 'iconoir-align-right',
        },
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
