<template>
  <div
    v-if="value !== null"
    class="array-field__item"
    :class="{ 'cell-error': value === 'NaN' }"
  >
    <div class="array-field__ellipsis">
      {{
        value === 'NaN'
          ? $t('fieldErrors.invalidNumber')
          : formatFrontendNumber(field, value)
      }}
    </div>
  </div>
</template>

<script>
import { formatDecimalNumber } from '@baserow/modules/database/utils/number'

export default {
  name: 'FunctionalFormulaArrayNumberItem',
  props: {
    value: {
      type: null,
      default: null,
    },
    field: {
      type: Object,
      required: true,
    },
  },
  methods: {
    formatFrontendNumber(field, value) {
      return formatDecimalNumber(field, value)
    },
  },
}
</script>
