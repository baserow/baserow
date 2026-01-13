<template>
  <div ref="cell" class="grid-view__cell">
    <client-only>
      <div class="grid-field-date">
        <div ref="dateDisplay" class="grid-field-date__date">
          {{ getDate(field, value) || value }}
        </div>
        <div
          v-if="field.date_include_time"
          ref="timeDisplay"
          class="grid-field-date__time"
        >
          {{ getTime(field, value) }}
        </div>
        <div v-if="field.date_show_tzinfo" class="grid-field-date__tzinfo">
          {{ getCellTimezoneAbbr(field, value) }}
        </div>
      </div>
    </client-only>
  </div>
</template>

<script>
import readOnlyDateField from '@baserow/modules/database/mixins/readOnlyDateField'

export default {
  name: 'FunctionalGridViewFieldDate',
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
