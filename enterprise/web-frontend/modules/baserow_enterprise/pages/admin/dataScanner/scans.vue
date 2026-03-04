<template>
  <DataScannerScansTab @view-results="viewResults" />
</template>

<script>
import DataScannerScansTab from '@baserow_enterprise/components/admin/dataScanner/DataScannerScansTab'

export default {
  name: 'DataScannerScansPage',
  components: { DataScannerScansTab },
  methods: {
    viewResults(scan) {
      this.$router.push({
        name: 'admin-data-scanner-results',
        query: { scan_id: scan.id, scan_name: scan.name },
      })
    },
  },
}
</script>
