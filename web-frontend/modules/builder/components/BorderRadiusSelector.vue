<template>
  <RadioGroup
    :model-value="value"
    :options="borderRadiusOptions"
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
    borderRadiusOptions() {
      return [
        {
          title: this.$t('borderRadiusSelector.pixel'),
          value: BORDER_RADIUS_TYPES.PIXEL,
          icon: 'iconoir-cursor-pointer',
        },
        {
          title: this.$t('borderRadiusSelector.percent'),
          value: BORDER_RADIUS_TYPES.PERCENT,
          icon: 'iconoir-percentage',
        },
      ]
    },
  },
}
</script>
