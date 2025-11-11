<template>
  <Modal @hidden="hidden">
    <div v-if="loadingViews" class="loading-overlay"></div>
    <h2 class="box__title">
      {{ $t('regenerateAIFieldModal.title', { name: field.name }) }}
    </h2>
    <Error :error="error"></Error>
    <RegenerateAIFieldForm
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
      <RegenerateAIFieldLoadingBar
        :job="job"
        :loading="loading"
        :disabled="!isValid"
        :field="field"
        @close="hide()"
      >
      </RegenerateAIFieldLoadingBar>
    </RegenerateAIFieldForm>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import ViewService from '@baserow/modules/database/services/view'
import FieldService from '@baserow_premium/services/field'
import JobService from '@baserow/modules/core/services/job'
import { populateView } from '@baserow/modules/database/store/view'
import RegenerateAIFieldForm from '@baserow_premium/components/field/RegenerateAIFieldForm'
import RegenerateAIFieldLoadingBar from '@baserow_premium/components/field/RegenerateAIFieldLoadingBar'

export default {
  name: 'RegenerateAIFieldModal',
  components: { RegenerateAIFieldForm, RegenerateAIFieldLoadingBar },
  mixins: [modal, error],
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
      job: null,
      pollInterval: null,
      isValid: false,
    }
  },
  computed: {
    jobHasFailed() {
      return ['failed', 'cancelled'].includes(this.job?.state)
    },
    jobIsRunning() {
      return (
        this.job !== null && this.job.state !== 'finished' && !this.jobHasFailed
      )
    },
  },
  methods: {
    async show(...args) {
      const show = modal.methods.show.call(this, ...args)
      this.job = null
      this.loading = false
      await this.fetchViews()
      this.$nextTick(() => {
        this.valuesChanged()
      })
      return show
    },
    hidden(...args) {
      this.stopPollIfRunning()
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
        // Call the AI field regeneration service
        const { data } = await FieldService(
          this.$client
        ).regenerateAIFieldValues(this.field.id, {
          viewId: values.view_id,
          rowIds: null, // null means use view or table mode
          onlyEmpty: values.skip_populated,
        })
        this.job = data
        if (this.pollInterval !== null) {
          clearInterval(this.pollInterval)
        }
        this.pollInterval = setInterval(this.getLatestJobInfo, 1000)
      } catch (error) {
        this.stopPollAndHandleError(error)
      }
    },
    async getLatestJobInfo() {
      try {
        // Poll the job status using the generic JobService
        const { data } = await JobService(this.$client).get(this.job.id)
        this.job = data
        if (!this.jobIsRunning) {
          this.loading = false
          this.stopPollIfRunning()
        }
        if (this.jobHasFailed) {
          const title =
            this.job.state === 'failed'
              ? this.$t('regenerateAIFieldModal.failedTitle')
              : this.$t('regenerateAIFieldModal.cancelledTitle')
          const message =
            this.job.state === 'failed'
              ? this.$t('regenerateAIFieldModal.failedDescription')
              : this.$t('regenerateAIFieldModal.cancelledDescription')
          this.showError(title, message)
        }
      } catch (error) {
        this.stopPollAndHandleError(error)
      }
    },
    stopPollAndHandleError(error) {
      this.loading = false
      this.stopPollIfRunning()
      this.handleError(error, 'regenerate')
    },
    stopPollIfRunning() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval)
      }
    },
    valuesChanged() {
      this.isValid = this.$refs.form.isFormValid()
      this.job = null
    },
  },
}
</script>
