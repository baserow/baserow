<template functional>
  <div
    v-if="props.value !== null"
    class="array-field__item"
    :class="{
      'cell-error': props.value === 'NaN',
    }"
  >
    <div class="array-field__ellipsis">
      {{
        props.value === 'NaN'
          ? parent.$t('fieldErrors.invalidNumber')
          : $options.methods.formatFrontendNumber(props.field, props.value)
      }}
    </div>
  </div>
</template>

<script>
import { formatDecimalNumber } from '@baserow/modules/database/utils/number'

export default {
  name: 'FunctionalFormulaArrayNumberItem',
  methods: {
    formatFrontendNumber(field, value) {
      return formatDecimalNumber(field, value)
    },
  },
}
</script>
