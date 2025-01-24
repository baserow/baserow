<template>
  <div v-if="!loadedProperties">
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
        :value="syncedProperties.includes(property.key)"
        :disabled="property.unique_primary || jobIsRunning || jobHasSucceeded"
        @input="toggleVisibleField(property.key)"
      >
        <i :class="getFieldTypeIconClass(property.field_type)"></i>
        {{ property.name }}</SwitchInput
      >
    </FormGroup>
    <Error :error="error"></Error>
    <div class="modal-progress__actions margin-top-2">
      <ProgressBar
        v-if="jobIsRunning || jobHasSucceeded"
        :value="job.progress_percentage"
        :status="jobHumanReadableState"
      />
      <div class="align-right">
        <Button
          type="primary"
          size="large"
          :disabled="creatingTable || jobIsRunning || jobHasSucceeded"
          :loading="creatingTable || jobIsRunning || jobHasSucceeded"
          @click="create"
        >
          {{ $t('createDataSync.create') }}
        </Button>
      </div>
    </div>
  </div>
</template>

<script>
import TableForm from '@baserow/modules/database/components/table/TableForm'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import DataSyncService from '@baserow/modules/database/services/dataSync'
import { clone } from '@baserow/modules/core/utils/object'
import dataSync from '@baserow/modules/database/mixins/dataSync'

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
  data() {
    return {
      formValues: null,
      properties: null,
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
    },
  },
}
</script>
