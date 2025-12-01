<template functional>
  <div class="card-text">
    {{ $options.methods.formatValue(props.field, props.value) }}
  </div>
</template>

<script>
import numberField from '@baserow/modules/database/mixins/numberField'
import { formatDecimalNumber } from '@baserow/modules/database/utils/number'

export default {
  height: 16,
  mixins: [numberField],
  methods: {
    formatValue(field, value) {
      return formatDecimalNumber(field, value)
    },
  },
}
</script>
