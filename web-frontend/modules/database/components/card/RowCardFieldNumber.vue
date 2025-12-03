<template>
  <div class="card-text">
    {{ formatValue(field, value) }}
  </div>
</template>

<script>
import numberField from '@baserow/modules/database/mixins/numberField'
import { formatDecimalNumber } from '@baserow/modules/database/utils/number'

export default {
  name: 'RowCardFieldNumber',
  height: 16,
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
  mixins: [numberField],
  methods: {
    formatValue(field, value) {
      return formatDecimalNumber(field, value)
    },
  },
}
</script>
