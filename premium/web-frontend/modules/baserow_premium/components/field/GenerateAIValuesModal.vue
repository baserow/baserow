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
import job from '@baserow/modules/core/mixins/job'
import { GenerateAIValuesJobType } from '@baserow_premium/jobTypes'

export default {
  name: 'GenerateAIValuesModal',
  components: { GenerateAIValuesForm, GenerateAIValuesFormFooter },
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
      isValid: false,
    }
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
      this.$nextTick(() => {
        this.valuesChanged()
      })
      return show
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
    onJobFinished() {
      this.job = null
      this.loading = false
    },
    onJobFailed() {
      this.loading = false
    },
    onJobCancelled() {
      this.loading = false
      this.cancelLoading = false
    },
    valuesChanged() {
      this.isValid = this.$refs.form.isFormValid()
    },
  },
}
</script>
