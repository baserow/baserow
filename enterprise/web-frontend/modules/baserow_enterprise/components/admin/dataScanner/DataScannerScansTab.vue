<template>
  <div>
    <CrudTable
      ref="crudTable"
      :service="service"
      :columns="columns"
      row-id-key="id"
      @row-context="onRowContext"
      @rows-update="onRowsUpdate"
    >
      <template #empty>
        <div class="placeholder">
          <div class="placeholder__icon">
            <i class="iconoir-search"></i>
          </div>
          <h2 class="placeholder__header">
            {{ $t('dataScanner.emptyTitle') }}
          </h2>
          <p class="placeholder__content">
            {{ $t('dataScanner.emptyDescription') }}
          </p>
          <div class="placeholder__action">
            <Button type="primary" size="large" @click="openCreateModal">
              {{ $t('dataScanner.createScan') }}
            </Button>
          </div>
        </div>
      </template>
      <template #title>
        {{ $t('dataScanner.title') }}
      </template>
      <template #header-right-side>
        <Button
          type="primary"
          size="large"
          class="margin-left-2"
          @click="openCreateModal"
        >
          {{ $t('dataScanner.createScan') }}
        </Button>
      </template>
      <template #menus="slotProps">
        <DataScanActionsContext
          ref="actionsContext"
          :scan="focusedScan"
          @edit="handleEdit"
          @deleted="slotProps.deleteRow"
          @triggered="handleTriggered"
          @view-results="handleViewResults"
        />
      </template>
    </CrudTable>
    <DataScanModal ref="createModal" @saved="handleSaved" />
    <DataScanModal ref="editModal" :scan="focusedScan" @saved="handleUpdated" />
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import { DataScannerScansService } from '@baserow_enterprise/services/dataScanner'
import DataScanStatusField from '@baserow_enterprise/components/admin/dataScanner/DataScanStatusField'
import DataScanTypeField from '@baserow_enterprise/components/admin/dataScanner/DataScanTypeField'
import DataScanFrequencyField from '@baserow_enterprise/components/admin/dataScanner/DataScanFrequencyField'
import DataScanLastRunField from '@baserow_enterprise/components/admin/dataScanner/DataScanLastRunField'
import DataScanResultsCountField from '@baserow_enterprise/components/admin/dataScanner/DataScanResultsCountField'
import DataScanActionsContext from '@baserow_enterprise/components/admin/dataScanner/DataScanActionsContext'
import DataScanModal from '@baserow_enterprise/components/admin/modals/DataScanModal'

const POLL_INTERVAL_MS = 2000

export default {
  name: 'DataScannerScansTab',
  components: {
    CrudTable,
    DataScanActionsContext,
    DataScanModal,
  },
  emits: ['view-results'],
  data() {
    return {
      focusedScan: {},
      pollTimerId: null,
    }
  },
  beforeUnmount() {
    this.stopPolling()
  },
  computed: {
    service() {
      return DataScannerScansService(this.$client)
    },
    columns() {
      return [
        new CrudTableColumn(
          'name',
          this.$t('dataScanner.nameColumn'),
          SimpleField,
          true,
          true
        ),
        new CrudTableColumn(
          'scan_type',
          this.$t('dataScanner.typeColumn'),
          DataScanTypeField,
          true
        ),
        new CrudTableColumn(
          'frequency',
          this.$t('dataScanner.frequencyColumn'),
          DataScanFrequencyField,
          true
        ),
        new CrudTableColumn(
          'status',
          this.$t('dataScanner.statusColumn'),
          DataScanStatusField,
          false
        ),
        new CrudTableColumn(
          'last_run',
          this.$t('dataScanner.lastRunColumn'),
          DataScanLastRunField,
          false
        ),
        new CrudTableColumn(
          'results_count',
          this.$t('dataScanner.resultsCountColumn'),
          DataScanResultsCountField,
          false,
          false,
          false,
          { onViewResults: this.handleViewResults }
        ),
        new CrudTableColumn('more', '', MoreField, false, false, true),
      ]
    },
  },
  methods: {
    openCreateModal() {
      this.$refs.createModal.show()
    },
    handleEdit(scan) {
      this.focusedScan = scan
      this.$refs.editModal.show()
    },
    handleSaved(scan) {
      this.$refs.crudTable.rows.push(scan)
    },
    handleUpdated(scan) {
      this.$refs.crudTable.updateRow(scan)
      this.$refs.crudTable.refresh()
    },
    handleTriggered(scan) {
      this.$refs.crudTable.updateRow({
        ...scan,
        is_running: true,
        last_run_started_at: moment.utc().format(),
      })
      this.ensurePolling()
    },
    handleViewResults(scan) {
      this.$emit('view-results', scan)
    },
    onRowsUpdate(rows) {
      if (rows.some((r) => r.is_running)) {
        this.ensurePolling()
      }
    },
    ensurePolling() {
      if (this.pollTimerId !== null) {
        return
      }
      this.pollTimerId = setTimeout(
        () => this.pollRunningScans(),
        POLL_INTERVAL_MS
      )
    },
    stopPolling() {
      if (this.pollTimerId !== null) {
        clearTimeout(this.pollTimerId)
        this.pollTimerId = null
      }
    },
    async pollRunningScans() {
      this.pollTimerId = null

      const crudTable = this.$refs.crudTable
      if (!crudTable) {
        return
      }

      const runningScans = crudTable.rows.filter((r) => r.is_running)
      if (runningScans.length === 0) {
        return
      }

      for (const scan of runningScans) {
        try {
          const { data } = await this.service.get(scan.id)
          crudTable.updateRow(data)
        } catch {
          // Scan may have been deleted; ignore.
        }
      }

      const stillRunning = crudTable.rows.some((r) => r.is_running)
      if (stillRunning) {
        this.pollTimerId = setTimeout(
          () => this.pollRunningScans(),
          POLL_INTERVAL_MS
        )
      }
    },
    onRowContext({ row, event, target }) {
      event.preventDefault()
      let horizontal = 'right'
      if (target === undefined) {
        target = {
          left: event.clientX,
          top: event.clientY,
        }
        horizontal = 'left'
      }
      const action = row.id === this.focusedScan.id ? 'toggle' : 'show'
      this.focusedScan = row
      this.$refs.actionsContext[action](target, 'bottom', horizontal, 4)
    },
  },
}
</script>
