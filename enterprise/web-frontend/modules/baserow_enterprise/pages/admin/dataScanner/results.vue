<template>
  <DataScannerResultsTab :initial-scan-filter="initialScanFilter" />
</template>

<script>
import DataScannerResultsTab from '@baserow_enterprise/components/admin/dataScanner/DataScannerResultsTab'

export default {
  name: 'DataScannerResultsPage',
  components: { DataScannerResultsTab },
  computed: {
    initialScanFilter() {
      const scanId = parseInt(this.$route.query.scan_id, 10)
      const scanName = this.$route.query.scan_name
      if (scanId && scanName) {
        return { id: scanId, name: scanName }
      }
      return null
    },
  },
}
</script>
