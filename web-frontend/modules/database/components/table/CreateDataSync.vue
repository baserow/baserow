<template>
  <div v-if="restoredFromStore" class="margin-top-3 margin-bottom-3">
    <p class="margin-bottom-2">{{ $t('createDataSync.syncing') }}</p>
    <div class="modal-progress__actions">
      <ProgressBar
        v-if="jobIsRunning || jobIsFinished"
        :value="job.progress_percentage"
        :status="jobHumanReadableState"
      />
      <ButtonText
        v-if="jobIsRunning || cancelLoading"
        tag="a"
        type="secondary"
        class="modal-progress__cancel-button"
        :loading="cancelLoading"
        @click="cancelJob"
      >
        {{ $t('action.cancel') }}
      </ButtonText>
    </div>
  </div>
  <div v-else-if="!loadedProperties">
    <TableForm
      ref="tableForm"
      class="margin-top-3 margin-bottom-2"
      :default-name="getDefaultName()"
      @submitted="submitted"
    >
      <component :is="dataSyncComponent" :disabled="loadingProperties" />
    </TableForm>
    <Error :error="error"></Error>
    <div class="align-right">
      <Button
        type="primary"
        size="large"
        :disabled="loadingProperties"
        :loading="loadingProperties"
        @click="$refs.tableForm.submit()"
      >
        {{ $t('createDataSync.next') }}
      </Button>
    </div>
  </div>
  <div v-else>
    <FormGroup small-label class="margin-top-3">
      <template #label> {{ $t('createDataSync.fields') }}</template>
      <SwitchInput
        v-for="property in orderedProperties"
        :key="property.key"
        class="margin-top-2"
        small
        :value="syncedProperties.includes(property.key) || autoAddNewProperties"
        :disabled="
          property.unique_primary ||
          autoAddNewProperties ||
          jobIsRunning ||
          jobIsFinished
        "
        @input="toggleVisibleField(property.key)"
      >
        <i :class="getFieldTypeIconClass(property.field_type)"></i>
        {{ property.name }}</SwitchInput
      >
    </FormGroup>
    <FormGroup
      small-label
      class="margin-top-2"
      :helper-text="$t('createDataSync.autoAddHelper')"
    >
      <SwitchInput
        v-model="autoAddNewProperties"
        class="margin-top-2"
        small
        :disabled="jobIsRunning || jobIsFinished"
      >
        {{ $t('createDataSync.autoAddLabel') }}</SwitchInput
      >
    </FormGroup>
    <FormGroup
      v-if="twoWaySyncStrategy"
      small-label
      class="margin-top-2"
      :helper-text="twoWaySyncStrategy.getDescription()"
    >
      <SwitchInput
        v-model="twoWaySync"
        class="margin-top-2"
        small
        :disabled="jobIsRunning || jobIsFinished || isTwoWaySyncDeactivated"
        @click="clickTwoWaySync"
      >
        {{ $t('createDataSync.twoWaySyncLabel') }}
        <i v-if="isTwoWaySyncDeactivated" class="iconoir-lock"></i>
      </SwitchInput>
    </FormGroup>
    <component
      :is="twoWaySyncDeactivatedModal[0]"
      v-if="twoWaySyncDeactivatedModal !== null"
      ref="twoWaySyncDeactivatedModal"
      v-bind="twoWaySyncDeactivatedModal[1]"
    ></component>
    <Error :error="error"></Error>
    <div class="modal-progress__actions margin-top-2">
      <ProgressBar
        v-if="jobIsRunning || jobIsFinished"
        :value="job.progress_percentage"
        :status="jobHumanReadableState"
      />
      <ButtonText
        v-if="jobIsRunning || cancelLoading"
        tag="a"
        type="secondary"
        class="modal-progress__cancel-button"
        :loading="cancelLoading"
        @click="cancelJob"
      >
        {{ $t('action.cancel') }}
      </ButtonText>
      <Button
        type="primary"
        size="large"
        full-width
        class="modal-progress__primary-button"
        :disabled="creatingTable || jobIsFinished || jobIsRunning"
        :loading="creatingTable || jobIsFinished || jobIsRunning"
        @click="create"
      >
        {{ $t('createDataSync.create') }}
      </Button>
    </div>
  </div>
</template>

<script>
import TableForm from '@baserow/modules/database/components/table/TableForm'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import DataSyncService from '@baserow/modules/database/services/dataSync'
import { clone } from '@baserow/modules/core/utils/object'
import dataSync from '@baserow/modules/database/mixins/dataSync'
import { SyncDataSyncTableJobType } from '@baserow/modules/database/jobTypes'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick, useNuxtApp } from '#imports'

export default {
  name: 'CreateDataSync',
  components: { TableForm },
  mixins: [dataSync],
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
  emits: ['hide', 'import-in-progress', 'uploading-before-job-created'],
  setup() {
    const nuxtApp = useNuxtApp()
    return { nuxtApp }
  },
  data() {
    return {
      restoredFromStore: false,
      formValues: null,
      properties: null,
      creatingTable: false,
      createdTable: null,
      autoAddNewProperties: false,
      twoWaySync: false,
    }
  },
  computed: {
    dataSyncType() {
      if (this.chosenType === '') return null
      try {
        return this.$registry.get('dataSync', this.chosenType)
      } catch {
        return null
      }
    },
    dataSyncComponent() {
      return this.dataSyncType ? this.dataSyncType.getFormComponent() : null
    },
    twoWaySyncStrategy() {
      if (!this.dataSyncType) return null
      const strategy = this.dataSyncType.getTwoWayDataSyncStrategy()
      if (!strategy) {
        return null
      }

      return this.$registry.get('twoWaySyncStrategy', strategy)
    },
    isTwoWaySyncDeactivated() {
      if (!this.twoWaySyncStrategy) {
        return true
      }
      return this.twoWaySyncStrategy.isDeactivated(this.database.workspace.id)
    },
    syncInProgress() {
      return this.creatingTable || this.jobIsRunning
    },
    // True while creating the table before the sync job exists.
    // Once created, the user can close the modal and the job will restore on reopen.
    uploadingBeforeJobCreated() {
      return this.creatingTable && this.job === null
    },
    twoWaySyncDeactivatedModal() {
      if (!this.twoWaySyncStrategy) {
        return null
      }
      return this.twoWaySyncStrategy.getDeactivatedClickModal()
    },
  },
  watch: {
    syncInProgress: {
      handler(value) {
        this.$emit('import-in-progress', value)
      },
      immediate: true,
    },
    uploadingBeforeJobCreated: {
      handler(value) {
        this.$emit('uploading-before-job-created', value)
      },
      immediate: true,
    },
    chosenType(newValue, oldValue) {
      if (newValue !== oldValue) {
        this.hideError()
        this.loadedProperties = false
        this.loadingProperties = false
        this.formValues = null
        this.properties = null
        this.syncedProperties = null
        this.creatingTable = false
        this.createdTable = null
      }
    },
  },
  mounted() {
    this.loadRunningJob()
  },
  methods: {
    hide() {},
    loadRunningJob() {
      const runningJob = this.$store.getters['job/getUnfinishedJobs'].find(
        (j) =>
          j.type === SyncDataSyncTableJobType.getType() &&
          j.data_sync?.database_id === this.database.id &&
          j.data_sync?.last_sync === null
      )
      if (runningJob) {
        this.job = runningJob
        this.restoredFromStore = true
      }
    },
    getDefaultName() {
      const excludeNames = this.database.tables.map((table) => table.name)
      const baseName = this.$t('createTableModal.defaultName')
      return getNextAvailableNameInSequence(baseName, excludeNames)
    },
    async submitted(formValues) {
      this.formValues = formValues
      await this.fetchNonExistingProperties(this.chosenType, formValues)
    },
    async create() {
      this.hideError()
      this.job = null
      this.uploadProgressPercentage = 0

      const formValues = clone(this.formValues)
      formValues.table_name = formValues.name
      formValues.synced_properties = this.syncedProperties
      formValues.auto_add_new_properties = this.autoAddNewProperties
      formValues.two_way_sync = this.twoWaySync

      this.creatingTable = true
      this.hideError()

      try {
        const { data } = await DataSyncService(this.$client).create(
          this.database.id,
          formValues
        )
        this.createdTable = data
        await this.$store.dispatch('table/forceUpsert', {
          database: this.database,
          data: this.createdTable,
        })
        await this.syncTable(this.createdTable)
      } catch (error) {
        if (error.handler && error.handler.code === 'ERROR_SYNC_ERROR') {
          this.showError(
            this.$t('dataSyncType.syncError'),
            error.handler.detail
          )
          error.handler.handled()
          return
        }
        this.handleError(error)
      } finally {
        this.creatingTable = false
      }
    },
    async onJobFinished() {
      const tableId = this.createdTable?.id || this.job?.data_sync?.table_id
      if (tableId) {
        await this.$router.push({
          name: 'database-table',
          params: {
            databaseId: this.database.id,
            tableId,
          },
        })
        await pageFinished(this.nuxtApp)
        await nextTick()
      }
      this.restoredFromStore = false
      this.$emit('hide')
    },
    onJobCancelled() {
      // Optimistically delete the table since the backend may take time to cancel the job
      const tableId = this.job.data_sync?.table_id
      if (!tableId) return

      const table = this.database.tables.find((t) => t.id === tableId)
      if (!table) return

      this.$store.dispatch('table/forceDelete', {
        database: this.database,
        table,
      })

      this.restoredFromStore = false
      this.job = null
    },
    clickTwoWaySync() {
      if (this.isTwoWaySyncDeactivated) {
        this.$refs.twoWaySyncDeactivatedModal.show()
      }
    },
  },
}
</script>
