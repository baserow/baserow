<template>
  <FormInput
    :value="value"
    :default-value-when-empty="defaultValueWhenEmpty"
    type="number"
    remove-number-input-controls
    :to-value="(value) => (value ? parseInt(value) : null)"
    :style="{
      width: '100px',
    }"
    @input="$emit('input', $event)"
    @blur="$emit('blur')"
  >
    <template #suffix>px</template>
  </FormInput>
</template>

<script>
export default {
  name: 'PixelValueSelector',
  props: {
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
}
</script>
