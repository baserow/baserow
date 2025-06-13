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
  name: 'FunctionalGridViewFieldNumber',
  functional: true,
  methods: {
    formatFrontendNumber(field, value) {
      return formatDecimalNumber(field, value)
    },
  },
}
</script>
