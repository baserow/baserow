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
        newJobs.forEach((storeJob) => {
          const index = this.previousJobs.findIndex((j) => j.id === storeJob.id)
          if (index !== -1) {
            this.$set(this.previousJobs, index, {
              ...this.previousJobs[index],
              progress_percentage: storeJob.progress_percentage,
              state: storeJob.state,
              updated_on: storeJob.updated_on,
            })
          }
        })

        const runningJobIds = newJobs.map((j) => j.id)
        const finishedJobs = this.previousJobs.filter(
          (j) =>
            (j.state === 'pending' || j.state === 'started') &&
            !runningJobIds.includes(j.id)
        )

        if (finishedJobs.length > 0) {
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
      this.loadingNewJobs = true
      try {
        const { data } = await FieldService(
          this.$client
        ).listGenerateAIValuesJobs(this.field.id)
        const jobs = data?.results || []

        const storeJobs = this.unfinishedJobsFromStore
        let addedRunningJobs = false

        jobs.forEach((job, index) => {
          const storeJob = storeJobs.find((sj) => sj.id === job.id)
          if (storeJob) {
            jobs[index] = {
              ...job,
              progress_percentage: storeJob.progress_percentage,
              state: storeJob.state,
              updated_on: storeJob.updated_on,
            }
          } else if (job.state === 'pending' || job.state === 'started') {
            this.$store.dispatch('job/forceCreate', {
              ...job,
              type: GenerateAIValuesJobType.getType(),
            })
            addedRunningJobs = true
          }
        })

        if (addedRunningJobs) {
          this.$store.dispatch('job/tryScheduleNextUpdate')
        }

        // Filter out the current job being shown in the form to avoid duplication
        this.previousJobs = jobs.filter((job) => job.id !== this.job?.id)
      } catch (error) {
        this.handleError(error)
      } finally {
        this.jobListLoading = false
        this.loadingNewJobs = false
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
        const job = this.previousJobs.find((j) => j.id === jobId)
        if (job) {
          await this.$store.dispatch('job/cancel', job)
          if (job.row_ids && job.row_ids.length > 0 && job.field_id) {
            this.$store.dispatch('page/view/grid/setPendingFieldOperations', {
              fieldId: job.field_id,
              rowIds: job.row_ids,
              value: false,
            })
          }
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
