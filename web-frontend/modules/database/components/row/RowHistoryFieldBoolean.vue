<template>
  <div class="row-history-entry__field-content">
    <div v-if="before">
      <div
        class="row-history-entry__diff row-history-entry__diff--removed row-history-field-boolean__diff"
      >
        <i class="iconoir-check"></i>
      </div>
    </div>
    <div v-if="after">
      <div
        class="row-history-entry__diff row-history-entry__diff--added row-history-field-boolean__diff"
      >
        <i class="iconoir-check"></i>
      </div>
    </div>
  </div>
</template>

<script>
import { trueValues } from '@baserow/modules/core/utils/constants'

export default {
  name: 'RowHistoryFieldBoolean',
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
  computed: {
    before() {
      return trueValues.includes(this.entry.before[this.fieldIdentifier])
    },
    after() {
      return trueValues.includes(this.entry.after[this.fieldIdentifier])
    },
  },
}
</script>
