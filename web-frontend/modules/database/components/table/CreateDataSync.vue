<template>
  <div v-if="!loadedProperties">
    <TableForm
      ref="tableForm"
      class="margin-bottom-2"
      :default-name="getDefaultName()"
      @submitted="submitted"
    >
      <component :is="dataSyncComponent" />
    </TableForm>
    <Error :error="error"></Error>
  </div>
  <div v-else>
    <FormGroup small-label>
      <template #label> {{ $t('createDataSync.fields') }}</template>
      <SwitchInput
        v-for="property in properties"
        :key="property.key"
        class="margin-top-2"
        small
        :value="syncedProperties.includes(property.key)"
        :disabled="property.unique_primary || jobIsRunning || jobHasSucceeded"
        @input="toggleVisibleField(property.key)"
      >
        <i :class="getFieldTypeIconClass(property.field_type)"></i>
        {{ property.name }}</SwitchInput
      >
    </FormGroup>
    <Error :error="error"></Error>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import jobProgress from '@baserow/modules/core/mixins/jobProgress'
import TableForm from '@baserow/modules/database/components/table/TableForm'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import DataSyncService from '@baserow/modules/database/services/dataSync'
import { clone } from '@baserow/modules/core/utils/object'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'

export default {
  name: 'CreateDataSync',
  components: { TableForm },
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
      loadingProperties: false,
      loadedProperties: false,
      formValues: null,
      properties: null,
      syncedProperties: null,
      creatingTable: false,
      createdTable: null,
    }
  },
  computed: {
    dataSyncComponent() {
      return this.chosenType === ''
        ? null
        : this.$registry.get('dataSync', this.chosenType).getFormComponent()
    },
  },
  watch: {
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
    loadedProperties(newVal) {
      this.$emit('loaded-properties-changed', newVal)
    },
    loadingProperties(newVal) {
      this.$emit('loading-properties-changed', newVal)
    },
    jobIsRunning(newVal) {
      this.$emit('job-is-running-changed', newVal)
    },
    jobHasSucceeded(newVal) {
      this.$emit('job-has-succeeded-changed', newVal)
    },
    creatingTable(newVal) {
      this.$emit('creating-table-changed', newVal)
    },
    job: {
      handler(newVal) {
        this.$emit('progress-percentage-changed', newVal.progress_percentage)
      },
      deep: true,
    },
    jobHumanReadableState(newVal) {
      this.$emit('job-human-readable-state-changed', newVal)
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
    getFieldTypeIconClass(fieldType) {
      return this.$registry.get('field', fieldType).getIconClass()
    },
    async submitted(formValues) {
      formValues.type = this.chosenType
      this.formValues = formValues

      this.loadingProperties = true
      this.hideError()

      try {
        const { data } = await DataSyncService(this.$client).fetchProperties(
          formValues
        )
        this.loadedProperties = true
        this.properties = data
        this.syncedProperties = data.map((p) => p.key)
      } catch (error) {
        this.handleError(error)
      } finally {
        this.loadingProperties = false
      }
    },
    toggleVisibleField(key) {
      const index = this.syncedProperties.findIndex((f) => key === f)
      if (index > -1) {
        this.syncedProperties.splice(index, 1)
      } else {
        this.syncedProperties.push(key)
      }
    },
    async create() {
      this.hideError()
      this.job = null
      this.uploadProgressPercentage = 0

      const formValues = clone(this.formValues)
      formValues.table_name = formValues.name
      formValues.synced_properties = this.syncedProperties

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
        const { data: job } = await DataSyncService(this.$client).syncTable(
          this.createdTable.data_sync.id
        )
        this.startJobPoller(job)
      } catch (error) {
        this.handleError(error)
      } finally {
        this.creatingTable = false
      }
    },
    async onJobDone() {
      await this.$nuxt.$router.push({
        name: 'database-table',
        params: {
          databaseId: this.database.id,
          tableId: this.createdTable.id,
        },
      })
      this.$emit('hide')
      this.$emit('job-has-succeeded-changed', false)
      this.loadedProperties = false
    },
    onJobFailed() {
      const error = new ResponseErrorMessage(
        this.$t('createDataSync.error'),
        this.job.human_readable_error
      )
      this.stopPollAndHandleError(error)
    },
    onJobPollingError(error) {
      this.stopPollAndHandleError(error)
    },
    stopPollAndHandleError(error) {
      this.stopPollIfRunning()
      error.handler ? this.handleError(error) : this.showError(error)
    },
    submit() {
      this.$refs.tableForm.submit()
    },
  },
}
</script>
