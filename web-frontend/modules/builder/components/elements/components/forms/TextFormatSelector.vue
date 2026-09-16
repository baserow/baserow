<template>
  <FormGroup
    :label="label || $t('textFormatSelector.label')"
    small-label
    required
    :horizontal="horizontal"
    class="margin-bottom-2"
  >
    <RadioGroup
      :model-value="modelValue"
      type="button"
      :options="options"
      @update:model-value="$emit('update:modelValue', $event)"
    />
  </FormGroup>
</template>

<script>
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'

/**
 * The Plain text / Markdown toggle shared by every form exposing a text
 * `format` setting.
 */
export default {
  name: 'TextFormatSelector',
  props: {
    modelValue: {
      type: String,
      required: false,
      default: TEXT_FORMAT_TYPES.PLAIN,
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
    options() {
      return [
        {
          value: TEXT_FORMAT_TYPES.PLAIN,
          label: this.$t('textFormatSelector.plain'),
        },
        {
          value: TEXT_FORMAT_TYPES.MARKDOWN,
          label: this.$t('textFormatSelector.markdown'),
        },
      ]
    },
  },
}
</script>
