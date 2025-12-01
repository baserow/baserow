<template>
  <Modal
    :right-sidebar="true"
    :right-sidebar-scrollable="true"
    :close-button="false"
    :can-close="!importInProgress"
    @show=";[(importer = ''), reset()]"
    @hide="stopPollIfRunning()"
  >
    <template #content>
      <div class="import-modal__header">
        <h2 class="import-modal__title">
          {{
            $t('importFileModal.additionalImportTitle', {
              table: table.name,
            })
          }}
        </h2>
        <div class="modal__actions"></div>
      </div>

      <div class="control margin-bottom-2">
        <FormGroup
          :label="$t('importFileModal.importLabel')"
          small-label
          required
        >
          <ul class="choice-items margin-top-1">
            <li v-for="importerType in importerTypes" :key="importerType.type">
              <a
                class="choice-items__link"
                :class="{ active: importer === importerType.type }"
                @click=";[(importer = importerType.type), reset()]"
              >
                <i
                  class="choice-items__icon"
                  :class="importerType.iconClass"
                ></i>
                <span> {{ importerType.getName() }}</span>
                <i
                  v-if="importer === importerType.type"
                  class="choice-items__icon-active iconoir-check-circle"
                ></i>
              </a>
            </li>
          </ul>
        </FormGroup>
      </div>

      <div class="margin-bottom-2">
        <component
          :is="importerComponent"
          :disabled="importInProgress"
          @changed="reset()"
          @header="onHeader($event)"
          @data="onData($event)"
          @getData="onGetData($event)"
        >
          <template #upsertMapping>
            <div class="control margin-top-1">
              <label class="control__label control__label--small">
                {{ $t('importFileModal.useUpsertField') }}
                <HelpIcon
                  :icon="'info-empty'"
                  :tooltip="$t('importFileModal.upsertTooltip')"
                />
              </label>
              <div class="control__elements">
                <Checkbox
                  v-model="useUpsertField"
                  :disabled="!mappingNotEmpty"
                  >{{ $t('common.yes') }}</Checkbox
                >
              </div>

              <Dropdown
                v-model="upsertField"
                :disabled="!useUpsertField"
                class="margin-top-1"
              >
                <DropdownItem
                  v-for="item in availableUpsertFields"
                  :key="item.id"
                  :name="item.name"
                  :value="item.id"
                />
              </Dropdown>
            </div>
          </template>
        </component>
      </div>

      <ImportErrorReport :job="job" :error="error"></ImportErrorReport>

      <Tabs v-if="dataLoaded" header-no-padding content-no-x-padding>
        <Tab :title="$t('importFileModal.importPreview')">
          <SimpleGrid
            class="import-modal__preview"
            :rows="previewImportData"
            :fields="fields"
          />
        </Tab>
        <Tab :title="$t('importFileModal.filePreview')">
          <SimpleGrid
            class="import-modal__preview"
            :rows="previewFileData"
            :fields="fileFields"
          />
        </Tab>
      </Tabs>

      <div v-if="!hasErrors" class="modal-progress__actions">
        <ProgressBar
          v-if="importInProgress && showProgressBar"
          :value="progressPercentage"
          :status="humanReadableState"
        />
        <div class="align-right">
          <Button
            type="primary"
            size="large"
            :loading="importInProgress || (jobHasSucceeded && !isTableCreated)"
            :disabled="
              importInProgress ||
              !canBeSubmitted ||
              (jobHasSucceeded && !isTableCreated)
            "
            @click="submitted"
          >
            {{ $t('importFileModal.importButton') }}
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
          {{ $t('importFileModal.showTable') }}
        </Button>
      </div>
    </template>
    <template #sidebar>
      <div class="import-modal__field-mapping">
        <div v-if="header.length > 0" class="import-modal__field-mapping-body">
          <h3>{{ $t('importFileModal.fieldMappingTitle') }}</h3>
          <p>
            {{ $t('importFileModal.fieldMappingDescription') }}
          </p>
          <FormGroup
            v-for="(head, index) in header"
            :key="head"
            :label="head"
            small-label
            required
            class="margin-bottom-2"
          >
            <Dropdown v-model="mapping[index]">
              <DropdownItem name="Skip" :value="0" icon="ban" />
              <DropdownItem
                v-for="field in availableFields"
                :key="field.id"
                :name="field.name"
                :value="field.id"
                :icon="field._.type.iconClass"
                :disabled="
                  selectedFields.includes(field.id) &&
                  field.id !== mapping[index]
                "
              />
            </Dropdown>
          </FormGroup>
        </div>
        <div v-else class="import-modal__field-mapping--empty">
          <i class="import-modal__field-mapping-empty-icon iconoir-shuffle" />
          <div class="import-modal__field-mapping-empty-text">
            {{ $t('importFileModal.selectImportMessage') }}
          </div>
        </div>
      </div>
      <div class="modal__actions">
        <a class="modal__close" @click="hide()">
          <i class="iconoir-cancel"></i>
        </a>
      </div>
    </template>
  </Modal>
</template>

<script>
import { clone } from '@baserow/modules/core/utils/object'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import jobProgress from '@baserow/modules/core/mixins/jobProgress'
import TableService from '@baserow/modules/database/services/table'
import {
  uuid,
  getNextAvailableNameInSequence,
} from '@baserow/modules/core/utils/string'
import SimpleGrid from '@baserow/modules/database/components/view/grid/SimpleGrid'
import _ from 'lodash'

import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import ImportErrorReport from '@baserow/modules/database/components/table/ImportErrorReport.vue'

export default {
  name: 'ImportFileModal',
  components: { ImportErrorReport, SimpleGrid },
  mixins: [modal, error, jobProgress],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: false,
      default: null,
    },
    fields: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  data() {
    return {
      importer: '',
      uploadProgressPercentage: 0,
      importState: null,
      showProgressBar: false,
      header: [],
      mapping: {},
      getData: null,
      previewData: [],
      dataLoaded: false,
      useUpsertField: false,
      upsertField: undefined,
    }
  },
  computed: {
    isTableCreated() {
      if (!this.job?.table_id) {
        return false
      }
      return this.database.tables.some(({ id }) => id === this.job.table_id)
    },
    mappingNotEmpty() {
      return Object.values(this.mapping).some(
        (value) => this.fieldIndexMap[value] !== undefined
      )
    },
    canBeSubmitted() {
      return (
        this.importer &&
        Object.values(this.mapping).some(
          (value) => this.fieldIndexMap[value] !== undefined
        ) &&
        (!this.useUpsertField ||
          Object.values(this.mapping).includes(this.upsertField))
      )
    },
    fieldTypes() {
      return this.$registry.getAll('field')
    },
    fileFields() {
      return this.header.map((header, index) => ({
        type: 'text',
        name: header,
        id: uuid(),
        order: index,
      }))
    },
    /**
     * All writable fields.
     */
    writableFields() {
      return this.fields.filter((field) =>
        this.fieldTypes[field.type].canWriteFieldValues(field)
      )
    },
    /**
     * Map beetween the field id and its index in the array.
     */
    fieldIndexMap() {
      return Object.fromEntries(
        this.writableFields.map((field, index) => [field.id, index])
      )
    },
    /**
     * All writable fields that can be imported into
     */
    availableFields() {
      return this.writableFields.filter(({ type }) =>
        this.fieldTypes[type].getCanImport()
      )
    },
    fieldMapping() {
      return Object.entries(this.mapping)
        .filter(
          ([, targetFieldId]) =>
            !!targetFieldId ||
            // Check if we have an id from a removed field
            this.fieldIndexMap[targetFieldId] !== undefined
        )
        .map(([importIndex, targetFieldId]) => {
          return [importIndex, this.fieldIndexMap[targetFieldId]]
        })
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
    previewImportData() {
      return this.previewData.map((row) => {
        const newRow = Object.fromEntries(
          this.fieldMapping.map(([importIndex, fieldIndex]) => {
            const field = this.writableFields[fieldIndex]
            return [
              `field_${field.id}`,
              this.fieldTypes[field.type].prepareValueForPaste(
                field,
                `${row[importIndex]}`,
                row[importIndex]
              ),
            ]
          })
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
    availableUpsertFields() {
      const selected = Object.values(this.mapping)
      return this.fields.filter((field) => {
        return (
          selected.includes(field.id) && this.fieldTypes[field.type].canUpsert()
        )
      })
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
      return this.state !== null && !this.jobIsDone && !this.error.visible
    },
    importerTypes() {
      return this.$registry.getAll('importer')
    },
    importerComponent() {
      return this.importer === ''
        ? null
        : this.$registry.get('importer', this.importer).getFormComponent()
    },
    humanReadableState() {
      switch (this.state) {
        case null:
          return ''
        case 'preparingData':
          return this.$t('importFileModal.preparing')
        case 'uploading':
          if (this.uploadProgressPercentage === 100) {
            return this.$t('job.statePending')
          } else {
            return this.$t('importFileModal.uploading')
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
    getDefaultName() {
      const excludeNames = this.database.tables.map((table) => table.name)
      const baseName = this.$t('importFileModal.defaultName')
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
          const foundField = this.availableFields.find(
            ({ name: fieldName }) => fieldName === name
          )
          return [index, foundField ? foundField.id : 0]
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
          const foundField = this.availableFields.find(
            ({ name: fieldName }) => fieldName === name
          )
          return [index, foundField ? foundField.id : 0]
        })
      )
    },
    /**
     * When the form is submitted we try to extract the initial data and first row
     * header setting from the values. An importer could have added those, but they
     * need to be removed from the values.
     */
    async submitted() {
      this.showProgressBar = false
      this.reset(false)
      let data = null
      const importConfiguration = {}

      if (this.upsertField) {
        // at the moment we use only one field, but the key may be composed of several
        // fields.
        importConfiguration.upsert_fields = [this.upsertField]
        importConfiguration.upsert_values = []
      }

      const mappedFieldIds = Object.values(this.mapping).filter(
        (id) => id !== 0
      )
      const skippedFieldIds = this.writableFields
        .filter((field) => !mappedFieldIds.includes(field.id))
        .map((field) => field.id)

      if (skippedFieldIds.length > 0) {
        importConfiguration.skipped_fields = skippedFieldIds
      }

      if (typeof this.getData === 'function') {
        try {
          this.showProgressBar = true
          this.importState = 'preparingData'
          await this.$ensureRender()

          data = await this.getData()
          const upsertFields = importConfiguration.upsert_fields || []
          const upsertValues = importConfiguration.upsert_values || []
          const upsertFieldIndexes = []

          Object.entries(this.mapping).forEach(
            ([importIndex, targetFieldId]) => {
              if (upsertFields.includes(targetFieldId)) {
                upsertFieldIndexes.push(importIndex)
              }
            }
          )

          const fieldMapping = Object.entries(this.mapping)
            .filter(
              ([, targetFieldId]) =>
                !!targetFieldId ||
                // Check if we have an id from a removed field
                this.fieldIndexMap[targetFieldId] !== undefined
            )
            .map(([importIndex, targetFieldId]) => {
              return [importIndex, this.fieldIndexMap[targetFieldId]]
            })

          // Template row with default values
          const defaultRow = this.writableFields.map((field) =>
            this.fieldTypes[field.type].getDefaultValue(field, true)
          )

          // Precompute the prepare value function for each field
          const prepareValueByField = this.writableFields.map(
            (field) => (value) =>
              this.fieldTypes[field.type].prepareValueForUpdate(
                field,
                this.fieldTypes[field.type].prepareValueForPaste(
                  field,
                  `${value}`,
                  value
                )
              )
          )

          // Processes the data by chunk to avoid UI freezes
          const result = []

          for (const chunk of _.chunk(data, 1000)) {
            result.push(
              chunk.map((row) => {
                const newRow = clone(defaultRow)
                const upsertRow = []
                fieldMapping.forEach(([importIndex, targetIndex]) => {
                  newRow[targetIndex] = prepareValueByField[targetIndex](
                    row[importIndex]
                  )
                  if (upsertFieldIndexes.includes(importIndex)) {
                    upsertRow.push(newRow[targetIndex])
                  }
                })

                if (upsertFields.length > 0 && upsertRow.length > 0) {
                  if (upsertFields.length !== upsertRow.length) {
                    throw new Error(
                      "upsert row length doesn't match required fields"
                    )
                  }
                  upsertValues.push(upsertRow)
                }
                return newRow
              })
            )
            await this.$ensureRender()
          }
          data = result.flat()
          if (upsertFields.length > 0) {
            if (upsertValues.length !== data.length) {
              throw new Error('upsert values lenght mismatch')
            }
            importConfiguration.upsert_values = upsertValues
          }
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

        const { data: job } = await TableService(this.$client).importData(
          this.table.id,
          data,
          {
            onUploadProgress,
          },
          importConfiguration.upsert_fields ? importConfiguration : null
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
        'row-import-creation': this.$t('importFileModal.stateRowCreation'),
        'row-import-validation': this.$t('importFileModal.statePreValidation'),
        'import-create-table': this.$t('importFileModal.stateCreateTable'),
      }
      return translations[jobState]
    },
    async openTable() {
      // Redirect to the newly created table.
      await this.$nuxt.$router.push({
        name: 'database-table',
        params: {
          databaseId: this.database.id,
          tableId: this.job.table_id,
        },
      })
      this.hide()
    },
    onJobDone() {
      this.$bus.$emit('table-refresh', {
        tableId: this.job.table_id,
      })
      if (!this.hasErrors) {
        this.hide()
      }
    },
    onJobFailed() {
      const error = new ResponseErrorMessage(
        this.$t('importFileModal.importError'),
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
