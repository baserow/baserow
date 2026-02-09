<template>
  <div class="card-text">
    {{ getDate(field, value) }}
    <template v-if="field.date_include_time">
      {{ getTime(field, value) }}
    </template>
    <span v-if="field.date_show_tzinfo" class="color--tzinfo">
      {{ getCellTimezoneAbbr(field, value) }}
    </span>
  </div>
</template>

<script>
import readOnlyDateField from '@baserow/modules/database/mixins/readOnlyDateField'

export default {
  height: 16,
  name: 'RowCardFieldDate',
  mixins: [readOnlyDateField],
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
}
</script>
