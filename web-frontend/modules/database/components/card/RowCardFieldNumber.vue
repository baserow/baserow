<template functional>
  <div class="card-text">
    {{ $options.methods.formatValue(props.field, props.value) }}
  </div>
</template>

<script>
import BigNumber from 'bignumber.js'
import numberField from '@baserow/modules/database/mixins/numberField'

export default {
  height: 16,
  mixins: [numberField],
  methods: {
    formatValue(field, value) {
      // Ensure proper formatting by treating the backend value as a BigNumber, no
      // matter what the field formatting is.
      return this.formatNumberValue(field, new BigNumber(value))
    },
  },
}
</script>
