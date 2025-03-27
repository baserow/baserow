<template>
  <RadioGroup
    :model-value="value"
    :options="options"
    type="button"
    @input="$emit('input', $event)"
  />
</template>

<script>
import { BORDER_RADIUS_TYPES } from '@baserow/modules/builder/enums'

export default {
  name: 'BorderRadiusSelector',
  props: {
    value: {
      type: String,
      required: false,
      default: null,
    },
  },
  computed: {
    options() {
      return [
        {
          label: this.$t('borderRadiusSelector.pixel'),
          value: BORDER_RADIUS_TYPES.PIXEL,
        },
        {
          label: this.$t('borderRadiusSelector.percent'),
          value: BORDER_RADIUS_TYPES.PERCENT,
        },
      ]
    },
  },
}
</script>
