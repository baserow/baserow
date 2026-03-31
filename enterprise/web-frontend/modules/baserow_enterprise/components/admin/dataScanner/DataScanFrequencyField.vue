<template>
  <span>{{ displayFrequency }}</span>
</template>

<script>
const FREQUENCY_MAP = {
  manual: 'dataScanner.frequencyManual',
  hourly: 'dataScanner.frequencyHourly',
  daily: 'dataScanner.frequencyDaily',
  weekly: 'dataScanner.frequencyWeekly',
}

export default {
  name: 'DataScanFrequencyField',
  props: {
    row: {
      type: Object,
      required: true,
    },
  },
  computed: {
    displayFrequency() {
      const key = FREQUENCY_MAP[this.row.frequency]
      return key ? this.$t(key) : this.row.frequency
    },
  },
}
</script>
