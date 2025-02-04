<template>
  <Modal @hidden="hidden">
    <div v-if="loadingViews" class="loading-overlay"></div>
    <h2 class="box__title">
      {{ $t('exportTableModal.title', { name: table.name }) }}
    </h2>
    <Error :error="error"></Error>
    <ExportTableForm
      ref="form"
      v-slot="{ filename }"
      :database="database"
      :table="table"
      :view="view"
      :views="views"
      :loading="loading"
      :enable-views-dropdown="enableViewsDropdown"
      @submitted="submitted"
      @values-changed="valuesChanged"
    >
      <ExportLoadingBar
        :job="job"
        :loading="loading"
        :disabled="!isValid"
        :filename="filename"
      >
      </ExportLoadingBar>
    </ExportTableForm>
  </Modal>
</template>

<script>
import { mapState } from 'vuex'

import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import ExporterService from '@baserow/modules/database/services/export'
import ViewService from '@baserow/modules/database/services/view'
import { populateView } from '@baserow/modules/database/store/view'
import ExportTableForm from '@baserow/modules/database/components/export/ExportTableForm'
import ExportLoadingBar from '@baserow/modules/database/components/export/ExportLoadingBar'

export default {
  name: 'ExportTableModal',
  components: { ExportTableForm, ExportLoadingBar },
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
    view: {
      type: Object,
      required: false,
      default: null,
    },
    startExport: {
      type: Function,
      required: false,
      default: function ({ table, values, client }) {
        return ExporterService(client).export(table.id, values)
      },
    },
    getJob: {
      type: Function,
      required: false,
      default: function (job, client) {
        return ExporterService(client).get(job.id)
      },
    },
    enableViewsDropdown: {
      type: Boolean,
      required: false,
      default: true,
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
      if (this.table._.selected) {
        this.views = this.selectedTableViews
        return
      }

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
        const { data } = await this.startExport({
          table: this.table,
          view: this.view,
          values,
          client: this.$client,
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
        const { data } = await this.getJob(this.job, this.$client)
        this.job = data
        if (!this.jobIsRunning) {
          this.loading = false
          this.stopPollIfRunning()
        }
        if (this.jobHasFailed) {
          const title =
            this.job.state === 'failed'
              ? this.$t('exportTableModal.failedTitle')
              : this.$t('exportTableModal.cancelledTitle')
          const message =
            this.job.state === 'failed'
              ? this.$t('exportTableModal.failedDescription')
              : this.$t('exportTableModal.cancelledDescription')
          this.showError(title, message)
        }
      } catch (error) {
        this.stopPollAndHandleError(error)
      }
    },
    stopPollAndHandleError(error) {
      this.loading = false
      this.stopPollIfRunning()
      this.handleError(error, 'export')
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
