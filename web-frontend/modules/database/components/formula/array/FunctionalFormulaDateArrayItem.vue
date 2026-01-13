<template>
  <div class="array-field__item">
    <div class="array-field__ellipsis">
      {{ getDate(field, value) }}
      <span v-if="field.date_include_time" class="array-field__time">
        {{ getTime(field, value) }}
      </span>
    </div>
  </div>
</template>

<script>
import readOnlyDateField from '@baserow/modules/database/mixins/readOnlyDateField'
export default {
  name: 'FunctionalFormulaDateArrayItem',
  mixins: [readOnlyDateField],
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
