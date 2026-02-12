<template>
  <Modal
    ref="modal"
    :can-close="!syncLoading && !jobIsRunning"
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
          v-if="syncLoading || jobIsRunning || jobHasSucceeded"
          :value="job?.progress_percentage || 0"
          :status="jobHumanReadableState"
        />
        <div class="align-right">
          <Button
            v-if="!jobHasSucceeded"
            type="primary"
            size="large"
            :disabled="syncLoading || jobIsRunning"
            :loading="syncLoading || jobIsRunning"
            @click="syncTable(table)"
          >
            {{ $t('syncTableModal.sync') }}
          </Button>
          <Button v-else type="secondary" size="large" @click="hide()">{{
            $t('syncTableModal.hide')
          }}</Button>
        </div>
      </div>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import dataSync from '@baserow/modules/database/mixins/dataSync'

export default {
  name: 'SyncTableModal',
  mixins: [modal, dataSync],
  props: {
    table: {
      type: Object,
      required: true,
    },
  },
  methods: {
    show() {
      this.job = null
      this.hideError()
      modal.methods.show.bind(this)()
    },
    hidden() {
      this.stopPollIfRunning()
    },
  },
}
</script>
