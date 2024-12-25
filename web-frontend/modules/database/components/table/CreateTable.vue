<template>
  <div>
    <TableForm
      ref="tableForm"
      class="margin-top-3 margin-bottom-2"
      :default-name="getDefaultName()"
      @submitted="submitted"
    >
      <component
        :is="importerComponent"
        :disabled="importInProgress"
        @changed="reset()"
        @header="onHeader($event)"
        @data="onData($event)"
        @getData="onGetData($event)"
      />
    </TableForm>

    <ImportErrorReport :job="job" :error="error"></ImportErrorReport>

    <SimpleGrid
      v-if="dataLoaded"
      class="import-modal__preview margin-bottom-2"
      :rows="previewFileData"
      :fields="fileFields"
    />

    <div v-if="!hasErrors" class="modal-progress__actions">
      <ProgressBar
        v-if="(importInProgress || jobHasSucceeded) && showProgressBar"
        :value="progressPercentage"
        :status="humanReadableState"
      />
      <div class="align-right">
        <Button
          type="primary"
          size="large"
          :loading="importInProgress || jobHasSucceeded"
          :disabled="importInProgress || jobHasSucceeded"
          @click="$refs.tableForm.submit()"
        >
          {{ $t('createTable.addButton') }}
        </Button>
      </div>
    </div>
    <div v-else class="align-right">
      <Button
        type="primary"
        size="large"
        :loading="!isTableCreated"
        @click="openTable()"
      >
        {{ $t('createTable.showTable') }}
      </Button>
    </div>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import jobProgress from '@baserow/modules/core/mixins/jobProgress'
import TableService from '@baserow/modules/database/services/table'
import {
  uuid,
  getNextAvailableNameInSequence,
} from '@baserow/modules/core/utils/string'
import SimpleGrid from '@baserow/modules/database/components/view/grid/SimpleGrid'
import TableForm from '@baserow/modules/database/components/table/TableForm'

import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import ImportErrorReport from '@baserow/modules/database/components/table/ImportErrorReport'

export default {
  name: 'CreateTable',
  components: { ImportErrorReport, TableForm, SimpleGrid },
  mixins: [error, jobProgress],
  props: {
    database: {
      type: Object,
      required: true,
    },
    chosenType: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      uploadProgressPercentage: 0,
      importState: null,
      showProgressBar: false,
      header: [],
      mapping: {},
      getData: null,
      previewData: [],
      dataLoaded: false,
    }
  },
  computed: {
    isTableCreated() {
      if (!this.job?.table_id) {
        return false
      }
      return this.database.tables.some(({ id }) => id === this.job.table_id)
    },
    fileFields() {
      return this.header.map((header, index) => ({
        type: 'text',
        name: header,
        id: uuid(),
        order: index,
      }))
    },
    previewFileData() {
      return this.previewData.map((row) => {
        const newRow = Object.fromEntries(
          this.fileFields.map((field, index) => [
            `field_${field.id}`,
            `${row[index]}`,
          ])
        )
        newRow.id = uuid()
        return newRow
      })
    },
    /**
     * Fields that are mapped to a column
     */
    selectedFields() {
      return Object.values(this.mapping)
    },
    progressPercentage() {
      switch (this.state) {
        case null:
          return 0
        case 'preparingData':
          return 1
        case 'uploading':
          // 10% -> 50%
          return (this.uploadProgressPercentage / 100) * 40 + 10
        default:
          // 50% -> 100%
          return 50 + this.job.progress_percentage / 2
      }
    },
    state() {
      if (this.job === null) {
        return this.importState
      } else {
        return this.job.state
      }
    },
    importInProgress() {
      return this.state !== null && !this.jobIsFinished && !this.error.visible
    },
    importerComponent() {
      return this.chosenType === ''
        ? null
        : this.$registry.get('importer', this.chosenType).getFormComponent()
    },
    humanReadableState() {
      switch (this.state) {
        case null:
          return ''
        case 'preparingData':
          return this.$t('createTable.preparing')
        case 'uploading':
          if (this.uploadProgressPercentage === 100) {
            return this.$t('job.statePending')
          } else {
            return this.$t('createTable.uploading')
          }
        default:
          return this.jobHumanReadableState
      }
    },
    hasErrors() {
      return this.job && Object.keys(this.job.report.failing_rows).length > 0
    },
  },
  beforeDestroy() {
    this.stopPollIfRunning()
  },
  methods: {
    hide() {
      this.stopPollIfRunning()
    },
    getDefaultName() {
      const excludeNames = this.database.tables.map((table) => table.name)
      const baseName = this.$t('createTableModal.defaultName')
      return getNextAvailableNameInSequence(baseName, excludeNames)
    },
    reset(full = true) {
      this.job = null
      this.uploadProgressPercentage = 0
      if (full) {
        this.header = []
        this.importState = null
        this.mapping = {}
        this.getData = null
        this.previewData = []
        this.dataLoaded = false
      }
      this.hideError()
    },
    onData({ header, previewData }) {
      this.header = header
      this.previewData = previewData
      this.mapping = Object.fromEntries(
        header.map((name, index) => {
          return [index, 0]
        })
      )
      this.dataLoaded = header.length > 0 || previewData.length > 0
    },
    onGetData(getData) {
      this.getData = getData
    },
    onHeader(header) {
      this.header = header
      this.mapping = Object.fromEntries(
        header.map((name, index) => {
          return [index, 0]
        })
      )
    },
    /**
     * When the form is submitted we try to extract the initial data and first row
     * header setting from the values. An importer could have added those, but they
     * need to be removed from the values.
     */
    async submitted(formValues) {
      this.showProgressBar = false
      this.reset(false)
      let data = null
      const values = { ...formValues }

      if (typeof this.getData === 'function') {
        try {
          this.showProgressBar = true
          this.importState = 'preparingData'
          await this.$ensureRender()
          data = await this.getData()
          data = [this.header, ...data]
        } catch (error) {
          this.reset()
          this.handleError(error, 'application')
        }
      }

      this.importState = 'uploading'

      const onUploadProgress = ({ loaded, total }) =>
        (this.uploadProgressPercentage = (loaded / total) * 100)

      try {
        if (data && data.length > 0) {
          this.showProgressBar = true
        }

        const { data: job } = await TableService(this.$client).create(
          this.database.id,
          values,
          data,
          true,
          {
            onUploadProgress,
          }
        )
        this.startJobPoller(job)
      } catch (error) {
        this.stopPollAndHandleError(error, {
          ERROR_MAX_JOB_COUNT_EXCEEDED: new ResponseErrorMessage(
            this.$t('job.errorJobAlreadyRunningTitle'),
            this.$t('job.errorJobAlreadyRunningDescription')
          ),
        })
      }
    },
    getCustomHumanReadableJobState(jobState) {
      const translations = {
        'row-import-creation': this.$t('createTable.stateRowCreation'),
        'row-import-validation': this.$t('createTable.statePreValidation'),
        'import-create-table': this.$t('createTable.stateCreateTable'),
      }
      return translations[jobState]
    },
    async openTable() {
      await this.$nuxt.$router.push({
        name: 'database-table',
        params: {
          databaseId: this.database.id,
          tableId: this.job.table_id,
        },
      })
      this.$emit('hide')
    },
    async onJobDone() {
      // Let's add the table to the store...
      const { data: table } = await TableService(this.$client).get(
        this.job.table_id
      )

      await this.$store.dispatch('table/forceUpsert', {
        database: this.database,
        data: table,
      })

      if (!this.hasErrors) {
        await this.openTable()
      }
    },
    onJobFailed() {
      const error = new ResponseErrorMessage(
        this.$t('createTable.importError'),
        this.job.human_readable_error
      )
      this.stopPollAndHandleError(error)
    },
    onJobPollingError(error) {
      this.stopPollAndHandleError(error)
    },
    stopPollAndHandleError(error, specificErrorMap = null) {
      this.stopPollIfRunning()
      error.handler
        ? this.handleError(error, 'application', specificErrorMap)
        : this.showError(error)
    },
  },
}
</script>
