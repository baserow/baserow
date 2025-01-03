<template functional>
  <div v-if="props.value !== null" class="array-field__item">
    <div class="array-field__ellipsis">
      {{ $options.methods.format(props.field, props.value) }}
    </div>
  </div>
</template>

<script>
import BigNumber from 'bignumber.js'
import { formatNumberValue } from '@baserow/modules/database/utils/number'

export default {
  name: 'FunctionalFormulaArrayNumberItem',
  methods: {
    format(field, value) {
      if (value == null || value === '') {
        return ''
      }
      return formatNumberValue(field, new BigNumber(value))
    },
  },
}
</script>
