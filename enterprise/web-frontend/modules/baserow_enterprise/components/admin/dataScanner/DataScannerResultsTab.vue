<template>
  <div>
    <CrudTable
      ref="crudTable"
      :service="service"
      :columns="columns"
      :filters="filters"
      :default-column-sorts="[{ key: 'first_identified_on', direction: 'asc' }]"
      :enable-search="false"
      row-id-key="id"
    >
      <template #empty>
        <div class="placeholder">
          <div class="placeholder__icon">
            <i class="iconoir-search"></i>
          </div>
          <h2 class="placeholder__header">
            {{ $t('dataScanner.emptyResultsTitle') }}
          </h2>
          <p class="placeholder__content">
            {{ $t('dataScanner.emptyResultsDescription') }}
          </p>
        </div>
      </template>
      <template #title>
        {{ $t('dataScanner.resultsTab') }}
      </template>
      <template #header-right-side>
        <Button type="primary" size="large" @click="$refs.exportModal.show()">
          {{ $t('dataScanner.exportToCsv') }}
        </Button>
      </template>
      <template #header-filters>
        <div class="data-scanner__filters">
          <FilterWrapper :name="$t('dataScanner.filterByScan')">
            <PaginatedDropdown
              ref="scanFilter"
              :value="filters.scan_id"
              :fetch-page="fetchScans"
              :empty-item-display-name="$t('dataScanner.allScans')"
              :not-selected-text="$t('dataScanner.allScans')"
              :initial-display-name="initialScanFilterName"
              value-name="name"
              @input="filterByScan"
            />
          </FilterWrapper>
          <Button
            class="data-scanner__clear-filters-button"
            type="secondary"
            @click="clearFilters"
          >
            {{ $t('dataScanner.clearFilters') }}
          </Button>
        </div>
      </template>
    </CrudTable>
    <DataScanExportModal ref="exportModal" :filters="filters" />
  </div>
</template>

<script>
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import LocalDateField from '@baserow/modules/core/components/crudTable/fields/LocalDateField'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import FilterWrapper from '@baserow_enterprise/components/crudTable/filters/FilterWrapper'
import DataScanResolveField from '@baserow_enterprise/components/admin/dataScanner/DataScanResolveField'
import DataScanRowLinkField from '@baserow_enterprise/components/admin/dataScanner/DataScanRowLinkField'
import DataScanExportModal from '@baserow_enterprise/components/admin/modals/DataScanExportModal'
import { DataScannerResultsService } from '@baserow_enterprise/services/dataScanner'
import baseService from '@baserow/modules/core/crudTable/baseService'

export default {
  name: 'DataScannerResultsTab',
  components: {
    CrudTable,
    FilterWrapper,
    PaginatedDropdown,
    DataScanExportModal,
  },
  props: {
    initialScanFilter: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      filters: { scan_id: this.initialScanFilter?.id || null },
      loading: true,
      initialScanFilterName: null,
    }
  },
  computed: {
    service() {
      return DataScannerResultsService(this.$client)
    },
    columns() {
      return [
        new CrudTableColumn(
          'scan_name',
          this.$t('dataScanner.scanNameColumn'),
          SimpleField,
          false
        ),
        new CrudTableColumn(
          'workspace_name',
          this.$t('dataScanner.workspaceColumn'),
          SimpleField,
          false
        ),
        new CrudTableColumn(
          'database_name',
          this.$t('dataScanner.databaseColumn'),
          SimpleField,
          false
        ),
        new CrudTableColumn(
          'table_name',
          this.$t('dataScanner.tableColumn'),
          SimpleField,
          false
        ),
        new CrudTableColumn(
          'field_name',
          this.$t('dataScanner.fieldColumn'),
          SimpleField,
          false
        ),
        new CrudTableColumn(
          'row_id',
          this.$t('dataScanner.rowIdColumn'),
          DataScanRowLinkField,
          false
        ),
        new CrudTableColumn(
          'matched_value',
          this.$t('dataScanner.matchedValueColumn'),
          SimpleField,
          false
        ),
        new CrudTableColumn(
          'first_identified_on',
          this.$t('dataScanner.firstIdentifiedColumn'),
          LocalDateField,
          true,
          false,
          false,
          { dateTimeFormat: 'L LTS' }
        ),
        new CrudTableColumn('resolve', '', DataScanResolveField, false),
      ]
    },
  },
  watch: {
    initialScanFilter: {
      handler(scan) {
        if (scan) {
          this.filters = { scan_id: scan.id }
          this.initialScanFilterName = scan.name
        }
      },
      immediate: true,
    },
  },
  methods: {
    fetchScans(page, search) {
      const scansUrl = '/admin/data-scanner/scans/'
      const scansPaginatedService = baseService(this.$client, scansUrl)
      return scansPaginatedService.fetch(scansUrl, page, search, [], {})
    },
    filterByScan(scanId) {
      this.filters = { ...this.filters, scan_id: scanId }
    },
    clearFilters() {
      this.$refs.scanFilter?.clear()
      this.filters = { scan_id: null }
    },
  },
}
</script>
