<template>
  <div>
    <form @submit.prevent="submit">
      <p class="margin-bottom-2">
        {{ $t('importFromAirtable.airtableShareLinkDescription') }}
        <br /><br />
        {{ $t('importFromAirtable.airtableShareLinkBeta') }}
      </p>
      <FormGroup
        :label="$t('importFromAirtable.airtableShareLinkTitle')"
        :error="$v.values.airtableUrl.$error"
        small-label
        required
        class="margin-bottom-2"
      >
        <FormInput
          v-model="values.airtableUrl"
          :error="$v.values.airtableUrl.$error"
          :placeholder="$t('importFromAirtable.airtableShareLinkPaste')"
          size="large"
          @blur="$v.values.airtableUrl.$touch()"
          @input="
            $emit(
              'input',
              $v.values.airtableUrl.$invalid ? '' : values.airtableUrl
            )
          "
        ></FormInput>
        <template #error>
          {{ $t('importFromAirtable.linkError') }}
        </template>
      </FormGroup>
    </form>
    <Error class="margin-bottom-0" :error="error"></Error>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import jobProgress from '@baserow/modules/core/mixins/jobProgress'
import AirtableService from '@baserow/modules/database/services/airtable'

export default {
  name: 'ImportFromAirtable',
  mixins: [error, jobProgress],
  data() {
    return {
      loading: false,
      values: {
        airtableUrl: '',
      },
    }
  },
  validations: {
    values: {
      airtableUrl: {
        valid(value) {
          const regex = /https:\/\/airtable.com\/[shr|app](.*)$/g
          return !!value.match(regex)
        },
      },
    },
  },
  computed: {
    ...mapGetters({
      selectedWorkspaceId: 'workspace/selectedId',
    }),
  },
  beforeDestroy() {
    this.stopPollIfRunning()
  },
  methods: {
    async submit() {
      this.$v.$touch()
      if (!this.$v.$invalid && !this.loading) {
        this.$emit('submit')
        if (this.loading) {
          return
        }

        this.loading = true
        this.hideError()

        try {
          const { data } = await AirtableService(this.$client).create(
            this.selectedWorkspaceId,
            this.values.airtableUrl
          )
          this.startJobPoller(data)
        } catch (error) {
          this.$emit('job-failed', {
            state: this.jobHumanReadableState,
          })
          this.stopPollAndHandleError(error, {
            ERROR_MAX_JOB_COUNT_EXCEEDED: new ResponseErrorMessage(
              this.$t('importFromAirtable.errorJobAlreadyRunningTitle'),
              this.$t('importFromAirtable.errorJobAlreadyRunningDescription')
            ),
          })
        }
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
      this.$emit('job-failed', {
        state: this.jobHumanReadableState,
      })
    },
    onJobPollingError(error) {
      this.stopPollAndHandleError(error)
      this.$emit('job-polling-error', {
        state: this.jobHumanReadableState,
      })
    },
    onJobDone() {
      this.$emit('job-done', {
        state: this.jobHumanReadableState,
        progress_percentage: this.job.progress_percentage,
        databaseId: this.job.database.id,
      })
    },
    onJobUpdated() {
      this.$emit('job-updated', {
        state: this.jobHumanReadableState,
        progress_percentage: this.job.progress_percentage,
      })
    },
  },
}
</script>
