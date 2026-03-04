<template>
  <a v-if="row.results_count > 0" @click.prevent="viewResults">
    {{ $t('dataScanner.results', row.results_count) }}
  </a>
  <span v-else>
    {{ $t('dataScanner.noResults') }}
  </span>
</template>

<script>
export default {
  name: 'DataScanResultsCountField',
  props: {
    row: {
      type: Object,
      required: true,
    },
    column: {
      type: Object,
      required: true,
    },
  },
  methods: {
    viewResults() {
      if (this.column.additionalProps.onViewResults) {
        this.column.additionalProps.onViewResults(this.row)
      }
    },
  },
}
</script>
