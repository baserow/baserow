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
  mixins: [numberField],
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
    formatValue(field, value) {
      return formatDecimalNumber(field, value)
    },
  },
}
</script>
