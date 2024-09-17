<template>
  <ModalV2
    :can-close="!jobIsRunning"
    :close-button="!jobIsRunning"
    @show="setChosenType('')"
    @hide="callCreateComponentHide()"
  >
    <template #header-content>
      <h2>
        {{ $t('createTableModal.title') }}
      </h2>
    </template>

    <template #content>
      <div class="control">
        <FormGroup
          :label="$t('createTableModal.importLabel')"
          small-label
          required
        >
          <ul class="choice-items margin-top-1">
            <li>
              <a
                class="choice-items__link"
                :class="{ active: chosenType === '' }"
                @click="setChosenType('')"
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
                :class="{ active: chosenType === instance.type }"
                @click="setChosenType(instance.type)"
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
              @selected="setChosenType(instance.type)"
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
        @import-in-progress-changed="importInProgress = $event"
        @job-is-running-changed="jobIsRunning = $event"
        @job-has-succeeded-changed="jobHasSucceeded = $event"
        @show-progress-bar-changed="showProgressBar = $event"
        @human-readable-state-changed="humanReadableState = $event"
        @progress-percentage-changed="progressPercentage = $event"
        @has-errors-changed="hasErrors = $event"
      ></CreateTable>
      <CreateDataSync
        v-else
        ref="createComponent"
        :chosen-type="chosenType"
        :database="database"
        @job-has-succeeded-changed="jobHasSucceeded = $event"
        @job-is-running-changed="jobIsRunning = $event"
        @job-human-readable-state-changed="humanReadableState = $event"
        @loaded-properties-changed="loadedProperties = $event"
        @loading-properties-changed="loadingProperties = $event"
        @creating-table-changed="creatingTable = $event"
        @progress-percentage-changed="progressPercentage = $event"
        @hide="hide()"
      ></CreateDataSync>
    </template>
    <template #footer-content>
      <template v-if="isImporter">
        <div v-if="!hasErrors">
          <ProgressBar
            v-if="(importInProgress || jobHasSucceeded) && showProgressBar"
            :value="progressPercentage"
            :status="humanReadableState"
          />

          <Button
            type="primary"
            size="large"
            :loading="importInProgress || jobHasSucceeded"
            :disabled="importInProgress || jobHasSucceeded"
            @click="$refs.createComponent.submit()"
          >
            {{ $t('createTable.addButton') }}
          </Button>
        </div>
        <Button
          v-else
          type="primary"
          size="large"
          :loading="!isTableCreated"
          @click="openTable()"
        >
          {{ $t('createTable.showTable') }}
        </Button>
      </template>
      <div v-else>
        <template v-if="!loadedProperties">
          <Button
            type="primary"
            size="large"
            :disabled="loadingProperties"
            :loading="loadingProperties"
            @click="$refs.createComponent.submit()"
          >
            {{ $t('createDataSync.next') }}
          </Button>
        </template>

        <template v-else>
          <ProgressBar
            v-if="jobIsRunning || jobHasSucceeded"
            :value="progressPercentage"
            :status="humanReadableState"
          />

          <Button
            type="primary"
            size="large"
            :disabled="creatingTable || jobIsRunning"
            :loading="creatingTable || jobIsRunning || jobHasSucceeded"
            @click="$refs.createComponent.create()"
          >
            {{ $t('createDataSync.create') }}
          </Button>
        </template>
      </div>
    </template>
  </ModalV2>
</template>

<script>
import modalv2 from '@baserow/modules/core/mixins/modalv2'
import CreateTable from '@baserow/modules/database/components/table/CreateTable'
import CreateDataSync from '@baserow/modules/database/components/table/CreateDataSync'
import DataSyncTypeChoice from '@baserow/modules/database/components/dataSync/DataSyncTypeChoice.vue'

export default {
  name: 'CreateTableModal',
  components: { DataSyncTypeChoice, CreateTable, CreateDataSync },
  mixins: [modalv2],
  props: {
    database: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      chosenType: '',
      humanReadableState: '',
      showProgressBar: false,
      importInProgress: false,
      jobHasSucceeded: false,
      jobIsRunning: false,
      progressPercentage: 0,
      loadedProperties: false,
      loadingProperties: false,
      creatingTable: false,
      hasErrors: false,
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
    callCreateComponentHide() {
      this.$refs.createComponent.hide()
    },
    setChosenType(type) {
      if (type === this.chosenType && type !== '') {
        return
      }
      this.chosenType = type
    },
  },
}
</script>
