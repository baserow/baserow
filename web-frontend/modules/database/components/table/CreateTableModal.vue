<template>
  <Modal
    ref="modal"
    :can-close="!uploadingBeforeJobCreated"
    @show="onShow"
    @hidden="callCreateComponentHide()"
  >
    <template #content>
      <div class="import-modal__header">
        <h2 class="import-modal__title">
          {{ $t('createTableModal.title') }}
        </h2>
      </div>

      <div class="control margin-bottom-2">
        <FormGroup
          :label="$t('createTableModal.importLabel')"
          small-label
          required
        >
          <ul class="choice-items margin-top-1">
            <li>
              <a
                class="choice-items__link"
                :class="{
                  active: chosenType === '',
                  disabled: importInProgress,
                }"
                @click="!importInProgress && setChosenType('')"
              >
                <i class="choice-items__icon iconoir-copy"></i>
                <span>{{ $t('createTableModal.newTable') }}</span>
                <i
                  v-if="chosenType === ''"
                  class="choice-items__icon-active iconoir-check-circle"
                ></i>
              </a>
            </li>
            <li v-for="instance in importerTypes" :key="instance.type">
              <a
                class="choice-items__link"
                :class="{
                  active: chosenType === instance.type,
                  disabled: importInProgress,
                }"
                @click="!importInProgress && setChosenType(instance.type)"
              >
                <i class="choice-items__icon" :class="instance.iconClass"></i>
                <span> {{ instance.getName() }}</span>
                <i
                  v-if="chosenType === instance.type"
                  class="choice-items__icon-active iconoir-check-circle"
                ></i>
              </a>
            </li>
            <DataSyncTypeChoice
              v-for="instance in dataSyncTypes"
              :key="instance.type"
              :active="chosenType === instance.type"
              :data-sync-type="instance"
              :database="database"
              :disabled="importInProgress"
              @selected="!importInProgress && setChosenType(instance.type)"
            ></DataSyncTypeChoice>
          </ul>
        </FormGroup>
      </div>

      <CreateTable
        v-if="isImporter"
        ref="createComponent"
        :chosen-type="chosenType"
        :database="database"
        @hide="hide()"
        @import-in-progress="importInProgress = $event"
        @uploading-before-job-created="uploadingBeforeJobCreated = $event"
      ></CreateTable>
      <CreateDataSync
        v-else
        ref="createComponent"
        :chosen-type="chosenType"
        :database="database"
        @hide="hide()"
        @import-in-progress="importInProgress = $event"
        @uploading-before-job-created="uploadingBeforeJobCreated = $event"
      ></CreateDataSync>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import CreateTable from '@baserow/modules/database/components/table/CreateTable'
import CreateDataSync from '@baserow/modules/database/components/table/CreateDataSync'
import DataSyncTypeChoice from '@baserow/modules/database/components/dataSync/DataSyncTypeChoice.vue'
import {
  FileImportJobType,
  SyncDataSyncTableJobType,
} from '@baserow/modules/database/jobTypes'

export default {
  name: 'CreateTableModal',
  components: { DataSyncTypeChoice, CreateTable, CreateDataSync },
  mixins: [modal],
  props: {
    database: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      chosenType: '',
      importInProgress: false,
      uploadingBeforeJobCreated: false,
    }
  },
  computed: {
    importerTypes() {
      return this.$registry.getAll('importer')
    },
    dataSyncTypes() {
      return this.$registry.getAll('dataSync')
    },
    isImporter() {
      return (
        this.chosenType === '' ||
        this.$registry.exists('importer', this.chosenType)
      )
    },
  },
  methods: {
    onShow() {
      const runningType = this.getRunningJobType()
      this.setChosenType(runningType || '')
    },
    getRunningJobType() {
      const jobs = this.$store.getters['job/getUnfinishedJobs']
      const databaseId = this.database.id

      // Check for a running file import (new table creation)
      const fileImport = jobs.find(
        (j) =>
          j.type === FileImportJobType.getType() &&
          j.table_id === null &&
          j.database_id === databaseId
      )
      if (fileImport) {
        const type = fileImport.importer_type || ''
        if (type && this.$registry.exists('importer', type)) {
          return type
        }
        return ''
      }

      // Check for a running data sync scoped to this database
      const dataSync = jobs.find(
        (j) =>
          j.type === SyncDataSyncTableJobType.getType() &&
          j.data_sync?.database_id === databaseId
      )
      if (dataSync) {
        const type = dataSync.data_sync?.type || ''
        if (type && this.$registry.exists('dataSync', type)) {
          return type
        }
        return ''
      }

      return null
    },
    callCreateComponentHide() {
      this.$refs.createComponent.hide()
    },
    setChosenType(type) {
      if (type === this.chosenType && type !== '') {
        return
      }
      this.chosenType = type
      this.$refs.createComponent?.reset()
    },
  },
}
</script>
