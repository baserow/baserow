<template>
  <div>
    {{
      localDate(
        row[column.key],
        column.additionalProps?.dateTimeFormat || 'L LT'
      )
    }}
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'

export default {
  name: 'LocalDateField',
  props: {
    row: {
      required: true,
      type: Object,
    },
    column: {
      required: true,
      type: Object,
    },
  },
  methods: {
    localDate(date, format) {
      if (date) {
        return moment.utc(date).local().format(format)
      } else {
        return ''
      }
    },
  },
}
</script>
