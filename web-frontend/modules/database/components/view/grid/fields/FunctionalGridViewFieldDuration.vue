<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-duration">
      {{ formatValue(field, value) }}
    </div>
  </div>
</template>

<script>
import { formatDurationValue } from '@baserow/modules/database/utils/duration'

export default {
  name: 'FunctionalGridViewFieldDuration',
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
      return formatDurationValue(value, field.duration_format)
    },
  },
}
</script>
