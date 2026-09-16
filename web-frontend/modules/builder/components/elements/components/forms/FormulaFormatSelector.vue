<template>
  <TextFormatSelector
    :model-value="format"
    :label="label"
    :horizontal="horizontal"
    @update:model-value="updateFormat"
  />
</template>

<script>
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import TextFormatSelector from '@baserow/modules/builder/components/elements/components/forms/TextFormatSelector'

/**
 * The Plain text / Markdown toggle of a formula surface. The format lives on
 * the formula object itself, next to its `mode`: the selector reads
 * `modelValue.format` and emits a copy of the object carrying the new one. A
 * missing key is the plain default; the backend returns the format explicitly
 * on every surface that supports one.
 */
export default {
  name: 'FormulaFormatSelector',
  components: { TextFormatSelector },
  props: {
    modelValue: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    label: {
      type: String,
      required: false,
      default: null,
    },
    horizontal: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['update:modelValue'],
  computed: {
    format() {
      return this.modelValue?.format || TEXT_FORMAT_TYPES.PLAIN
    },
  },
  methods: {
    updateFormat(format) {
      // A formula object always carries its expression, even an empty one.
      const formula = { formula: '', ...this.modelValue }
      delete formula.format
      if (format !== TEXT_FORMAT_TYPES.PLAIN) {
        formula.format = format
      }
      this.$emit('update:modelValue', formula)
    },
  },
}
</script>
