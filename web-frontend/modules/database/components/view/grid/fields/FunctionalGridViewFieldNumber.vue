<template functional>
  <div
    class="grid-view__cell"
    :class="{
      ...(data.staticClass && {
        [data.staticClass]: true,
      }),
      'cell-error': props.value === 'NaN',
    }"
  >
    <div class="grid-field-number">
      {{ $options.methods.formatNumberValue(props.field, props.value) }}
    </div>
  </div>
</template>

<script>
import { formatNumberValue } from '@baserow/modules/database/utils/number'
import BigNumber from 'bignumber.js'

export default {
  name: 'FunctionalGridViewFieldNumber',
  functional: true,
  methods: {
    formatNumberValue(field, value) {
      if (value == null || value === '') {
        return ''
      }
      return formatNumberValue(field, new BigNumber(value))
    },
  },
}
</script>
