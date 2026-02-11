<template>
  <div v-if="value !== null" class="array-field__item">
    <div class="array-field__ellipsis">
      {{ formatValue(field, value) }}
    </div>
  </div>
</template>

<script>
import durationField from '@baserow/modules/database/mixins/durationField'
export default {
  name: 'FunctionalFormulaArrayDurationItem',
  mixins: [durationField],
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
}
</script>
