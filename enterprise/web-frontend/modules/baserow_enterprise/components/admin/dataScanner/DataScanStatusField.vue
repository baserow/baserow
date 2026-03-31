<template>
  <div class="data-scan-status">
    <template v-if="row.is_running">
      <span class="flex align-items-center">
        <i class="loading"></i>
        {{ $t('dataScanner.runningSince', { time: formattedStartTime }) }}
      </span>
    </template>
    <template v-else>
      {{ $t('dataScanner.idle') }}
    </template>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'

export default {
  name: 'DataScanStatusField',
  props: {
    row: {
      type: Object,
      required: true,
    },
  },
  computed: {
    formattedStartTime() {
      if (!this.row.last_run_started_at) return ''
      return moment(this.row.last_run_started_at).fromNow()
    },
  },
}
</script>
