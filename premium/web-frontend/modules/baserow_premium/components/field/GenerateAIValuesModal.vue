<template>
  <Modal @hidden="hideError">
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
      <div v-if="loadingPreviousJobs" class="loading"></div>
      <div v-else-if="previousJobs.length > 0">
        <GenerateAIValuesJobListItem
          v-for="jobItem in previousJobs"
          :key="jobItem.id"
          :job-item="jobItem"
          :field="field"
          :views="views"
          :last-updated="
            jobItem.state === 'finished'
              ? jobItem.updated_on
              : jobItem.created_on
          "
        />
      </div>
      <div v-else class="margin-top-2">
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
      loading: false,
      isValid: false,
      views: [],
      loadingViews: false,
      previousJobs: [],
      loadingPreviousJobs: false,
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
    show(...args) {
      const show = modal.methods.show.call(this, ...args)
      // Don't await to avoid blocking the modal display
      this.loadRunningJob()
      this.fetchViews()
      this.loadPreviousJobs()
      this.$nextTick(() => {
        this.valuesChanged()
      })
      return show
    },
    async loadPreviousJobs() {
      this.loadingPreviousJobs = true

      try {
        const { data } = await FieldService(
          this.$client
        ).listGenerateAIValuesJobs(this.field.id)
        const jobs = data.jobs
        const storeJobs = this.unfinishedJobsFromStore
        let addedRunningJobs = false

        jobs.forEach((job, index) => {
          const storeJob = storeJobs.find((sj) => sj.id === job.id)
          if (storeJob) {
            jobs[index] = storeJob
          } else if (job.state === 'pending' || job.state === 'started') {
            this.$store.dispatch('job/forceCreate', job)
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
        this.loadingPreviousJobs = false
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
      } finally {
        this.loadingViews = false
      }
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
    // eslint-disable-next-line require-await
    async onJobFinished() {
      this.previousJobs.unshift(this.job)
      this.job = null
      this.loading = false
    },
    // eslint-disable-next-line require-await
    async onJobFailed() {
      this.previousJobs.unshift(this.job)
      this.job = null
      this.loading = false
    },
    // eslint-disable-next-line require-await
    async onJobCancelled() {
      this.previousJobs.unshift(this.job)
      this.job = null
      this.loading = false
    },
    valuesChanged() {
      this.isValid = this.$refs.form.isFormValid()
    },
  },
}
</script>
