<template>
  <FormGroup small-label :label="$t('widthSelector.width')" required>
    <RadioGroup
      v-model="value"
      type="button"
      :options="widthOptions"
      @input="$emit('input', $event)"
    ></RadioGroup>
  </FormGroup>
</template>

<script>
import { WIDTHS } from '@baserow/modules/builder/enums'

export default {
  name: 'WidthSelector',
  props: {
    value: {
      type: String,
      required: false,
      default: WIDTHS.AUTO.value,
    },
    widths: {
      type: Array,
      required: false,
      default: () => Object.values(WIDTHS),
    },
  },
  emits: ['input'],
  computed: {
    widthOptions() {
      return this.widths.map((width) => {
        return { label: this.$t(width.name), value: width.value }
      })
    },
  },
}
</script>
