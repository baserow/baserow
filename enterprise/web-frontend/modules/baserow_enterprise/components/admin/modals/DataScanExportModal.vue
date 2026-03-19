<template>
  <Modal ref="modal" @hidden="hidden">
    <h2 class="box__title">{{ $t('dataScanner.exportModalTitle') }}</h2>
    <Error :error="error"></Error>
    <DataScanExportForm ref="form" :loading="loading" @submitted="submitted">
      <ExportLoadingBar
        :job="job"
        :loading="loading"
        :filename="getExportedFilename(job)"
        :disabled="false"
      >
      </ExportLoadingBar>
    </DataScanExportForm>
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
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import job from '@baserow/modules/core/mixins/job'
import moment from '@baserow/modules/core/moment'
import { getHumanPeriodAgoCount } from '@baserow/modules/core/utils/date'
import ExportLoadingBar from '@baserow/modules/database/components/export/ExportLoadingBar'
import DataScanExportForm from '@baserow_enterprise/components/admin/forms/DataScanExportForm'
import { DataScannerResultsService } from '@baserow_enterprise/services/dataScanner'
import { DataScanResultExportJobType } from '@baserow_enterprise/jobTypes'

const MAX_EXPORT_FILES = 4

export default {
  name: 'DataScanExportModal',
  components: { DataScanExportForm, ExportLoadingBar },
  mixins: [modal, error, job],
  props: {
    filters: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      lastFinishedJobs: [],
    }
  },
  async mounted() {
    this.loading = true
    const jobs = await DataScannerResultsService(
      this.$client
    ).getLastExportJobs(MAX_EXPORT_FILES)
    this.lastFinishedJobs = jobs.filter((j) => j.state === 'finished')
    this.loadRunningJob()
    if (!this.jobIsRunning) {
      this.loading = false
    }
  },
  methods: {
    loadRunningJob() {
      const runningJob = this.$store.getters['job/getUnfinishedJobs'].find(
        (j) => j.type === DataScanResultExportJobType.getType()
      )
      if (runningJob) {
        this.job = runningJob
        this.loading = true
      }
    },
    getExportedFilename(j) {
      return j ? `data_scan_results_${j.created_on}.csv` : ''
    },
    getExportedFilenameTitle(j) {
      return this.$t('dataScanner.exportFilename', {
        date: this.localDate(j.created_on),
      })
    },
    humanExportedAt(timestamp) {
      const { period, count } = getHumanPeriodAgoCount(timestamp)
      return this.$t(`datetime.${period}Ago`, { count }, count)
    },
    hidden() {
      if (this.job && !this.jobIsRunning) {
        this.lastFinishedJobs = [this.job, ...this.lastFinishedJobs]
        this.job = null
      }
    },
    async submitted(values) {
      if (this.loading) return

      this.loading = true
      this.hideError()

      const payload = { ...values }

      if ('csv_include_header' in payload) {
        payload.csv_first_row_header = payload.csv_include_header
        delete payload.csv_include_header
      }

      if (this.filters.scan_id) {
        payload.filter_scan_id = this.filters.scan_id
      }

      try {
        const { data } = await DataScannerResultsService(
          this.$client
        ).startExportCsvJob(payload)
        this.lastFinishedJobs = this.lastFinishedJobs.slice(
          0,
          MAX_EXPORT_FILES - 1
        )
        await this.createAndMonitorJob(data)
      } catch (err) {
        this.loading = false
        this.handleError(err, 'export')
      }
    },
    onJobFinished() {
      this.loading = false
    },
    onJobFailed() {
      this.loading = false
      this.showError(
        this.$t('dataScanner.exportFailedTitle'),
        this.$t('dataScanner.exportFailedDescription')
      )
    },
    onJobCancelled() {
      this.loading = false
      this.showError(
        this.$t('dataScanner.exportCancelledTitle'),
        this.$t('dataScanner.exportCancelledDescription')
      )
    },
    localDate(date) {
      return moment.utc(date).local().format('L LT')
    },
  },
}
</script>
