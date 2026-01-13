<template>
  <div class="card-text">
    {{ formatValue(field, value) }}
  </div>
</template>

<script>
import durationField from '@baserow/modules/database/mixins/durationField'

export default {
  height: 16,
  name: 'RowCardFieldDuration',
  mixins: [durationField],
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
