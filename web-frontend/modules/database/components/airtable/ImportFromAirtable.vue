<template>
  <div>
    <AirtableImportForm @submitted="importFromAirtable">
      <Error :error="error"></Error>
      <div class="modal-progress__actions">
        <ProgressBar
          v-if="jobIsRunning || jobHasSucceeded"
          :value="job.progress_percentage"
          :status="jobHumanReadableState"
        />

        <Button
          v-if="!jobHasSucceeded"
          type="primary"
          size="large"
          class="modal-progress__export-button"
          :loading="loading"
          :disabled="loading"
        >
          {{ $t('importFromAirtable.importButtonLabel') }}
        </Button>

        <Button
          v-else
          type="secondary"
          size="large"
          class="modal-progress__export-button"
          @click="openDatabase"
        >
          {{ $t('importFromAirtable.openButtonLabel') }}</Button
        >
      </div>
    </AirtableImportForm>
  </div>
</template>

<script>
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import jobProgress from '@baserow/modules/core/mixins/jobProgress'
import AirtableService from '@baserow/modules/database/services/airtable'
import AirtableImportForm from '@baserow/modules/database/components/airtable/AirtableImportForm'

export default {
  name: 'ImportFromAirtable',
  components: { AirtableImportForm },
  mixins: [error, jobProgress],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  beforeDestroy() {
    this.stopPollIfRunning()
  },
  methods: {
    async importFromAirtable(values) {
      if (this.loading) {
        return
      }

      this.loading = true
      this.hideError()

      try {
        const { data } = await AirtableService(this.$client).create(
          this.workspace.id,
          values.airtableUrl,
          values.skipFiles,
          values.useSession ? values.session : null,
          values.useSession ? values.sessionSignature : null
        )
        this.startJobPoller(data)
      } catch (error) {
        this.stopPollAndHandleError(error, {
          ERROR_MAX_JOB_COUNT_EXCEEDED: new ResponseErrorMessage(
            this.$t('importFromAirtable.errorJobAlreadyRunningTitle'),
            this.$t('importFromAirtable.errorJobAlreadyRunningDescription')
          ),
        })
      }
    },
    stopPollAndHandleError(error, specificErrorMap = null) {
      this.loading = false
      this.stopPollIfRunning()
      error.handler
        ? this.handleError(error, 'airtable', specificErrorMap)
        : this.showError(error)
    },
    getCustomHumanReadableJobState(state) {
      const importingTablePrefix = 'importing-table-'
      if (state.startsWith(importingTablePrefix)) {
        const table = state.replace(importingTablePrefix, '')
        return this.$t('importFromAirtable.stateImportingTable', { table })
      }

      const translations = {
        'downloading-base': this.$t('importFromAirtable.stateDownloadingBase'),
        converting: this.$t('importFromAirtable.stateConverting'),
        'downloading-files': this.$t(
          'importFromAirtable.stateDownloadingFiles'
        ),
        importing: this.$t('importFromAirtable.stateImporting'),
      }
      return translations[state]
    },
    async openDatabase() {
      const application = this.$store.getters['application/get'](
        this.job.database.id
      )
      const type = this.$registry.get('application', application.type)
      if (await type.select(application, this)) {
        this.$emit('hidden')
      }
    },
    onJobFailed() {
      const error = new ResponseErrorMessage(
        this.$t('importFromAirtable.importError'),
        this.job.human_readable_error
      )
      this.stopPollAndHandleError(error)
    },
    onJobPollingError(error) {
      this.stopPollAndHandleError(error)
    },
  },
}
</script>
