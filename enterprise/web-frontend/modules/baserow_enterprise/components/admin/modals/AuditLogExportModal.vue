<template>
  <Modal @hidden="hidden">
    <h2 class="box__title">{{ $t('auditLogExportModal.title') }}</h2>
    <Error :error="error"></Error>
    <AuditLogExportForm ref="form" :loading="loading" @submitted="submitted">
      <ExportLoadingBar
        :job="job"
        :loading="loading"
        :filename="getExportedFilename(job)"
        :disabled="false"
      >
      </ExportLoadingBar>
    </AuditLogExportForm>
    <div
      v-if="lastFinishedJobs.length > 0 || job"
      class="audit-log__exported-list"
    >
      <div v-if="job" class="audit-log__exported-list-item">
        <div class="audit-log__exported-list-item-info">
          <div class="audit-log__exported-list-item-name">
            {{ getExportedFilenameTitle(job) }}
          </div>
          <div class="audit-log__exported-list-item-details">
            {{ humanExportedAt(job.created_on) }}
          </div>
        </div>
        <div>{{ job.progress_percentage }} %</div>
      </div>
      <div
        v-for="finishedJob in lastFinishedJobs"
        :key="finishedJob.id"
        class="audit-log__exported-list-item"
      >
        <div class="audit-log__exported-list-item-info">
          <div class="audit-log__exported-list-item-name">
            {{ getExportedFilenameTitle(finishedJob) }}
          </div>
          <div class="audit-log__exported-list-item-details">
            {{ humanExportedAt(finishedJob.created_on) }}
          </div>
        </div>
        <DownloadLink
          :url="finishedJob.url"
          :filename="getExportedFilename(finishedJob)"
          loading-class="button-icon--loading"
        >
          <template #default="{ loading: downloadLoading }">
            <div v-if="downloadLoading" class="loading"></div>
            <template v-else>{{
              $t('action.download').toLowerCase()
            }}</template>
          </template>
        </DownloadLink>
      </div>
    </div>
  </Modal>
</template>

<script>
import { mapState } from 'vuex'

import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import moment from '@baserow/modules/core/moment'
import { getHumanPeriodAgoCount } from '@baserow/modules/core/utils/date'
import ExportLoadingBar from '@baserow/modules/database/components/export/ExportLoadingBar'
import AuditLogExportForm from '@baserow_enterprise/components/admin/forms/AuditLogExportForm'
import AuditLogAdminService from '@baserow_enterprise/services/auditLog'

const MAX_EXPORT_FILES = 4

export default {
  name: 'AuditLogExportModal',
  components: { AuditLogExportForm, ExportLoadingBar },
  mixins: [modal, error],
  props: {
    filters: {
      type: Object,
      required: true,
    },
    workspaceId: {
      type: Number,
      default: null,
    },
  },
  data() {
    return {
      loading: false,
      timeoutId: null,
      timeNextPoll: 1000,
      job: null,
      lastFinishedJobs: [],
    }
  },
  async fetch() {
    this.loading = true
    const jobs = await AuditLogAdminService(this.$client).getLastExportJobs(
      MAX_EXPORT_FILES
    )
    const filteredJobs = this.workspaceId
      ? jobs.filter((job) => job.filter_workspace_id === this.workspaceId)
      : jobs
    this.lastFinishedJobs = filteredJobs.filter(
      (job) => job.state === 'finished'
    )
    const runningJob = filteredJobs.find(
      (job) => !['failed', 'cancelled', 'finished'].includes(job.state)
    )
    this.job = runningJob || null
    if (this.job) {
      this.scheduleNextPoll()
    } else {
      this.loading = false
    }
  },
  // the poll timeout can only be scheduled on the client
  fetchOnServer: false,
  computed: {
    jobHasFailed() {
      return ['failed', 'cancelled'].includes(this.job.state)
    },
    jobIsRunning() {
      return (
        this.job !== null && this.job.state !== 'finished' && !this.jobHasFailed
      )
    },
    ...mapState({
      selectedTableViews: (state) => state.view.items,
    }),
  },
  beforeDestroy() {
    this.stopPollIfRunning()
  },
  methods: {
    getExportedFilename(job) {
      return job ? `audit_log_${job.created_on}.csv` : ''
    },
    getExportedFilenameTitle(job) {
      if (job.filter_workspace_id) {
        return this.$t('auditLogExportModal.exportWorkspaceFilename', {
          date: this.localDate(job.created_on),
          workspaceId: job.filter_workspace_id,
        })
      } else {
        return this.$t('auditLogExportModal.exportFilename', {
          date: this.localDate(job.created_on),
        })
      }
    },
    humanExportedAt(timestamp) {
      const { period, count } = getHumanPeriodAgoCount(timestamp)
      return this.$tc(`datetime.${period}Ago`, count)
    },
    hidden() {
      this.stopPollIfRunning()
      if (this.job && !this.jobIsRunning) {
        this.lastFinishedJobs = [this.job, ...this.lastFinishedJobs]
        this.job = null
      }
    },
    async submitted(values) {
      if (!this.$refs.form.isFormValid()) {
        return
      }

      this.loading = true
      this.hideError()
      this.stopPollIfRunning()
      const filters = Object.fromEntries(
        Object.entries(this.filters).map(([key, value]) => [
          `filter_${key}`,
          value,
        ])
      )
      if (this.workspaceId) {
        filters.filter_workspace_id = this.workspaceId
        filters.exclude_columns = 'workspace_id,workspace_name'
      }

      try {
        const { data } = await AuditLogAdminService(
          this.$client
        ).startExportCsvJob({
          ...values,
          ...filters,
        })
        this.lastFinishedJobs = this.lastFinishedJobs.slice(
          0,
          MAX_EXPORT_FILES - 1
        )
        this.job = data
        this.scheduleNextPoll()
      } catch (error) {
        this.loading = false
        this.handleError(error, 'export')
      }
    },
    async getJobInfo() {
      try {
        const { data } = await AuditLogAdminService(
          this.$client
        ).getExportJobInfo(this.job.id)
        this.job = data

        if (this.jobIsRunning) {
          this.scheduleNextPoll()
          return
        }

        this.loading = false
        if (this.jobHasFailed) {
          let title, message
          if (this.job.status === 'failed') {
            title = this.$t('auditLogExportModal.failedTitle')
            message = this.$t('auditLogExportModal.failedDescription')
          } else {
            // cancelled
            title = this.$t('auditLogExportModal.cancelledTitle')
            message = this.$t('auditLogExportModal.cancelledDescription')
          }
          this.showError(title, message)
        }
      } catch (error) {
        this.handleError(error, 'export')
      }
    },
    scheduleNextPoll() {
      this.timeNextPoll = Math.min(this.timeNextPoll * 1.1, 5000)
      this.timeoutId = setTimeout(this.getJobInfo, this.timeNextPoll)
    },
    stopPollIfRunning() {
      clearTimeout(this.timeoutId)
      this.timeoutId = null
    },
    valuesChanged() {
      this.isValid = this.$refs.form.isFormValid()
    },
    localDate(date) {
      return moment.utc(date).local().format('L LT')
    },
  },
}
</script>
