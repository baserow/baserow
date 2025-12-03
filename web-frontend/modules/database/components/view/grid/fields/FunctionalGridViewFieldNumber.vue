<template>
  <div class="grid-view__cell" :class="{ 'cell-error': value === 'NaN' }">
    <div class="grid-field-number">
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
  name: 'FunctionalGridViewFieldNumber',
  props: {
    field: {
      type: Object,
      required: true,
    },
    value: {
      type: null,
      default: null,
    },
  },
  methods: {
    formatFrontendNumber(field, value) {
      return formatDecimalNumber(field, value)
    },
  },
}
</script>
