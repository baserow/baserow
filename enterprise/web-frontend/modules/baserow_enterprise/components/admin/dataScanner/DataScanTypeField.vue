<template>
  <span>{{ displayType }}</span>
</template>

<script>
const TYPE_MAP = {
  pattern: 'dataScanner.scanTypePattern',
  list_of_values: 'dataScanner.scanTypeListOfValues',
  list_table: 'dataScanner.scanTypeListTable',
}

export default {
  name: 'DataScanTypeField',
  props: {
    row: {
      type: Object,
      required: true,
    },
  },
  computed: {
    displayType() {
      const key = TYPE_MAP[this.row.scan_type]
      return key ? this.$t(key) : this.row.scan_type
    },
  },
}
</script>
