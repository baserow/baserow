<template>
  <div class="row-history-entry__field-content">
    <div v-if="entry.before[fieldIdentifier]">
      <div class="row-history-entry__diff row-history-entry__diff--removed">
        {{ formattedNumber(entry.before[fieldIdentifier]) }}
      </div>
    </div>
    <div v-if="entry.after[fieldIdentifier]">
      <div class="row-history-entry__diff row-history-entry__diff--added">
        {{ formattedNumber(entry.after[fieldIdentifier]) }}
      </div>
    </div>
  </div>
</template>

<script>
import { formatDecimalNumber } from '@baserow/modules/database/utils/number'

export default {
  name: 'RowHistoryFieldNumber',
  props: {
    entry: {
      type: Object,
      required: true,
    },
    fieldIdentifier: {
      type: String,
      required: true,
    },
    field: {
      type: Object,
      required: false,
      default: null,
    },
  },
  methods: {
    formattedNumber(value) {
      const metadata = this.entry.fields_metadata[this.fieldIdentifier]
      return formatDecimalNumber(metadata, value)
    },
  },
}
</script>
