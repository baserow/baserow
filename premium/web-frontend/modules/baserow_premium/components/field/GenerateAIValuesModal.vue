<template>
  <Modal>
    <div v-if="loadingViews" class="loading-overlay"></div>
    <h2 class="box__title">
      {{ $t('generateAIValuesModal.title', { name: field.name }) }}
    </h2>
    <Error :error="error"></Error>
    <GenerateAIValuesForm
      ref="form"
      :database="database"
      :table="table"
      :field="field"
      :view="view"
      :views="views"
      :loading="loading"
      @submitted="submitted"
      @values-changed="valuesChanged"
    >
      <GenerateAIValuesFormFooter
        :job="job"
        :loading="loading"
        :disabled="!isValid"
        :cancel-loading="cancelLoading"
        :field="field"
        @cancel-job="cancelJob(job.id)"
      >
      </GenerateAIValuesFormFooter>
    </GenerateAIValuesForm>

    <!-- Job List Section -->
    <div class="generate-ai-values__list">
      <div v-if="jobListLoading" class="loading"></div>
      <div v-else-if="previousJobs.length > 0">
        <GenerateAIValuesJobListItem
          v-for="jobItem in previousJobs"
          :key="jobItem.id"
          :job="jobItem"
          :field="field"
          :views="views"
          :cancel-loading="cancelLoading && cancellingJobId === jobItem.id"
          :last-updated="jobItem.updated_on"
          @cancel-job="cancelHistoryJob"
        />
      </div>
      <div v-else>
        {{ $t('generateAIValuesModal.noPreviousJobs') }}
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import ViewService from '@baserow/modules/database/services/view'
import FieldService from '@baserow_premium/services/field'
import { populateView } from '@baserow/modules/database/store/view'
import GenerateAIValuesForm from '@baserow_premium/components/field/GenerateAIValuesForm'
import GenerateAIValuesFormFooter from '@baserow_premium/components/field/GenerateAIValuesFormFooter'
import GenerateAIValuesJobListItem from '@baserow_premium/components/field/GenerateAIValuesJobListItem'
import job from '@baserow/modules/core/mixins/job'
import { GenerateAIValuesJobType } from '@baserow_premium/jobTypes'

export default {
  name: 'GenerateAIValuesModal',
  components: {
    GenerateAIValuesForm,
    GenerateAIValuesFormFooter,
    GenerateAIValuesJobListItem,
  },
  mixins: [modal, error, job],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      views: [],
      loadingViews: false,
      loading: false,
      cancelLoading: false,
      cancellingJobId: null,
      isValid: false,
      jobListLoading: false,
      previousJobs: [],
      loadingNewJobs: false,
    }
  },
  computed: {
    unfinishedJobsFromStore() {
      return this.$store.getters['job/getUnfinishedJobs'].filter(
        (job) =>
          job.type === GenerateAIValuesJobType.getType() &&
          job.field_id === this.field.id
      )
    },
  },
  watch: {
    unfinishedJobsFromStore: {
      async handler(newJobs) {
        // Update progress for running jobs in the list
        let hasNewJob = false
        newJobs.forEach((storeJob) => {
          const index = this.previousJobs.findIndex((j) => j.id === storeJob.id)
          if (index !== -1) {
            // Update existing job with latest progress and state
            this.$set(this.previousJobs, index, {
              ...this.previousJobs[index],
              progress_percentage: storeJob.progress_percentage,
              state: storeJob.state,
              updated_on: storeJob.updated_on,
            })
          } else {
            // New running job detected
            hasNewJob = true
          }
        })

        // Reload list once if there are new jobs and we're not already loading
        if (hasNewJob && !this.loadingNewJobs) {
          this.loadingNewJobs = true
          await this.loadPreviousJobs()
          this.loadingNewJobs = false
        }

        // Check if any jobs finished (no longer in unfinished list but were running)
        const runningJobIds = newJobs.map((j) => j.id)
        const finishedJobs = this.previousJobs.filter(
          (j) =>
            (j.state === 'pending' || j.state === 'started') &&
            !runningJobIds.includes(j.id)
        )

        if (finishedJobs.length > 0) {
          // Reload the list to get the updated states
          await this.loadPreviousJobs()
        }
      },
      deep: true,
    },
  },
  methods: {
    loadRunningJob() {
      const runningJob = this.$store.getters['job/getUnfinishedJobs'].find(
        (job) => {
          return (
            job.type === GenerateAIValuesJobType.getType() &&
            job.field_id === this.field.id &&
            job.row_ids === null
          )
        }
      )
      if (runningJob) {
        this.job = runningJob
        this.loading = true
      }
    },
    async show(...args) {
      const show = modal.methods.show.call(this, ...args)
      this.loading = false
      await this.fetchViews()
      this.loadRunningJob()
      await this.loadPreviousJobs()
      this.$nextTick(() => {
        this.valuesChanged()
      })
      return show
    },
    async loadPreviousJobs() {
      this.jobListLoading = true
      try {
        const { data } = await FieldService(
          this.$client
        ).listGenerateAIValuesJobs(this.field.id)
        this.previousJobs = data?.results || []
      } catch (error) {
        this.handleError(error)
      } finally {
        this.jobListLoading = false
      }
    },
    async fetchViews() {
      this.loadingViews = true
      try {
        const { data: viewsData } = await ViewService(this.$client).fetchAll(
          this.table.id
        )
        viewsData.forEach((v) => populateView(v, this.$registry))
        this.views = viewsData
      } catch (error) {
        this.handleError(error, 'views')
      }
      this.loadingViews = false
    },
    async submitted(values) {
      if (!this.$refs.form.isFormValid()) {
        return
      }

      this.loading = true
      this.hideError()

      try {
        const { data: job } = await FieldService(this.$client).generateAIValues(
          this.field.id,
          {
            viewId: values.view_id,
            onlyEmpty: values.skip_populated,
          }
        )
        await this.createAndMonitorJob(job)
      } catch (error) {
        this.loading = false
        this.handleError(error)
      }
    },
    async onJobFinished() {
      // Reload the job list to show the completed job
      await this.loadPreviousJobs()
      this.job = null
      this.loading = false
    },
    async onJobFailed() {
      await this.loadPreviousJobs()
      this.loading = false
    },
    async onJobCancelled() {
      await this.loadPreviousJobs()
      this.loading = false
      this.cancelLoading = false
    },
    valuesChanged() {
      this.isValid = this.$refs.form.isFormValid()
    },
    async cancelHistoryJob(jobId) {
      this.cancelLoading = true
      this.cancellingJobId = jobId
      try {
        // Find the job object from the list
        const job = this.previousJobs.find((j) => j.id === jobId)
        if (job) {
          await this.$store.dispatch('job/cancel', job)
          // Reload jobs to update the list
          await this.loadPreviousJobs()
        }
      } catch (error) {
        this.handleError(error)
      } finally {
        this.cancelLoading = false
        this.cancellingJobId = null
      }
    },
  },
}
</script>

<style lang="scss" scoped>
.generate-ai-values__list {
  border-top: 1px solid #d9dbde;
  padding-top: 30px;
  margin-top: 30px;
}
</style>
