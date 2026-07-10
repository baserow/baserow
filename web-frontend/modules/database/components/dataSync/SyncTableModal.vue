<template>
  <Modal
    ref="modal"
    :can-close="!syncLoading && (!jobIsRunning || attachedToForeignRun)"
    @hidden="hidden"
  >
    <template #content>
      <div class="import-modal__header">
        <h2 class="import-modal__title">
          {{ $t('syncTableModal.title', { name: table.name }) }}
        </h2>
      </div>
      <p>
        {{ $t('syncTableModal.description') }}
      </p>
      <Error :error="error"></Error>
      <div class="modal-progress__actions margin-top-2">
        <ProgressBar
          v-if="syncLoading || jobIsRunning || jobIsFinished"
          :value="job?.progress_percentage || 0"
          :status="jobHumanReadableState"
        />
        <div class="align-right">
          <Button
            v-if="!jobIsFinished"
            type="primary"
            size="large"
            :disabled="syncLoading || jobIsRunning"
            :loading="syncLoading || jobIsRunning"
            @click="startSync()"
          >
            {{ $t('syncTableModal.sync') }}
          </Button>
          <Button v-else type="secondary" size="large" @click="hide()">{{
            $t('syncTableModal.hide')
          }}</Button>
        </div>
      </div>
      <div v-if="table.data_sync" class="margin-top-3">
        <h3>{{ $t('dataSyncRuns.previousRuns') }}</h3>
        <DataSyncRunsList
          :data-sync-id="table.data_sync.id"
          @running-job="attachToRunningJob"
        />
      </div>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import dataSync from '@baserow/modules/database/mixins/dataSync'
import DataSyncRunsList from '@baserow/modules/database/components/dataSync/DataSyncRunsList'

export default {
  name: 'SyncTableModal',
  components: { DataSyncRunsList },
  mixins: [modal, dataSync],
  props: {
    table: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      attachedToForeignRun: false,
    }
  },
  methods: {
    show() {
      this.job = null
      this.attachedToForeignRun = false
      this.hideError()
      modal.methods.show.bind(this)()
    },
    startSync() {
      this.attachedToForeignRun = false
      return this.syncTable(this.table)
    },
    // Show an in-flight run's progress instead of failing with "already running".
    async attachToRunningJob(job) {
      if (!this.jobIsRunning) {
        this.attachedToForeignRun = true
        await this.createAndMonitorJob(job)
      }
    },
    hidden() {},
  },
}
</script>
