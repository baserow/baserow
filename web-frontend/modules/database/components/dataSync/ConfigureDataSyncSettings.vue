<template>
  <div>
    <h2 class="box__title">{{ $t('configureDataSyncSettings.title') }}</h2>
    <div v-if="fetchLoading">
      <div class="loading"></div>
    </div>
    <div v-if="!fetchLoaded">
      <Error :error="error"></Error>
    </div>
    <div v-else-if="fetchLoaded">
      <component
        :is="dataSyncComponent"
        ref="form"
        :default-values="dataSync"
        :update="true"
        :disabled="updateLoading || jobIsRunning"
        class="margin-bottom-2"
        @submitted="submitted"
        @values-changed="completed = false"
      />

      <Error :error="error"></Error>
      <div class="modal-progress__actions">
        <ProgressBar
          v-if="jobIsRunning || jobHasSucceeded"
          :value="job.progress_percentage"
          :status="jobHumanReadableState"
        />
        <div class="align-right">
          <div class="flex">
            <Button
              v-if="completed"
              tag="a"
              type="secondary"
              size="large"
              @click="$emit('hide')"
              >{{ $t('action.hide') }}</Button
            >
            <template v-if="!completed">
              <Checkbox
                v-model="syncTableValue"
                :disabled="updateLoading || jobIsRunning"
                >{{ $t('configureDataSyncSettings.syncTable') }}</Checkbox
              >
              <Button
                type="primary"
                size="large"
                :loading="updateLoading || jobIsRunning"
                :disabled="updateLoading || jobIsRunning"
                @click="$refs.form.submit()"
              >
                {{ $t('action.save') }}
              </Button>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import dataSync from '@baserow/modules/database/mixins/dataSync'
import DataSyncService from '@baserow/modules/database/services/dataSync'
import TableForm from '@baserow/modules/database/components/table/TableForm.vue'

export default {
  name: 'ConfigureDataSyncSettings',
  components: { TableForm },
  mixins: [dataSync],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      fetchLoading: false,
      fetchLoaded: false,
      dataSync: null,
      completed: false,
      syncTableValue: true,
    }
  },
  computed: {
    dataSyncComponent() {
      return this.$registry
        .get('dataSync', this.dataSync.type)
        .getFormComponent()
    },
  },
  mounted() {
    this.hideError()
    this.fetchDataSource(this.table)
  },
  methods: {
    onJobDone() {
      this.completed = true
    },
    async fetchDataSource(table) {
      this.fetchLoading = true

      try {
        const { data } = await DataSyncService(this.$client).get(
          table.data_sync.id
        )
        this.dataSync = data
        this.fetchLoaded = true
      } catch (error) {
        this.handleError(error)
      } finally {
        this.fetchLoading = false
      }
    },
    async submitted(values) {
      // Remove the `undefined` values, because those contain not updated secrets that
      // are only meant to be included in the update request if they've changed
      // because they're not exposed by the backend.
      const valuesWithoutUndefined = Object.fromEntries(
        Object.entries(values).filter(([_, v]) => v !== undefined)
      )
      await this.update(this.table, valuesWithoutUndefined, this.syncTableValue)
      if (!this.syncTableValue) {
        this.completed = true
      }
    },
  },
}
</script>
