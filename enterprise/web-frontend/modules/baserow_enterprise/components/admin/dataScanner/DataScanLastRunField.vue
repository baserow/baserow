<template>
  <span v-if="row.last_run_finished_at">
    {{ formattedTime }}
  </span>
  <span v-else>
    {{ $t('dataScanner.neverRun') }}
  </span>
</template>

<script>
import moment from '@baserow/modules/core/moment'

export default {
  name: 'DataScanLastRunField',
  props: {
    row: {
      type: Object,
      required: true,
    },
  },
  computed: {
    formattedTime() {
      if (!this.row.last_run_finished_at) return ''
      return moment(this.row.last_run_finished_at).fromNow()
    },
  },
}
</script>
