<template>
  <ModalV2
    :can-close="!job.isRunning"
    :close-button="!job.isRunning"
    @show="loading = false"
    @hidden="handleHidden"
  >
    <template #header-content>
      <h2>
        {{ $t('action.createNew') }} {{ applicationType.getName() | lowercase }}
      </h2>
    </template>

    <template #content>
      <Error :error="error"></Error>

      <component
        :is="applicationType.getApplicationFormComponent()"
        ref="applicationForm"
        :default-name="getDefaultName()"
        :loading="loading"
        @submitted="submitted"
        @airtable-submitted="handleAirtableSubmitted"
        @job-done="handleJobDone($event)"
        @job-updated="handleJobUpdated($event)"
        @job-failed="handleJobFailed($event)"
        @job-polling-error="handleJobFailed($event)"
        @import-type-changed="importType = $event"
      >
      </component>
    </template>

    <template #footer-content>
      <component
        :is="applicationType.getApplicationFormFooterComponent()"
        ref="applicationFormFooter"
        :application-type="applicationType"
        :import-type="importType"
        :loading="loading"
        :job="job"
        @submit="handleSubmit"
        @open-database="handleOpenDatabase"
      >
      </component>
    </template>
  </ModalV2>
</template>

<script>
import modalv2 from '@baserow/modules/core/mixins/modalv2'
import error from '@baserow/modules/core/mixins/error'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'

export default {
  name: 'CreateApplicationModal',
  mixins: [modalv2, error],
  props: {
    applicationType: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      importType: null,
      job: {
        hasSucceeded: false,
        isRunning: false,
        status: '',
        progressPercentage: 0,
        databaseId: null,
      },
    }
  },
  computed: {},
  methods: {
    getDefaultName() {
      const excludeNames = this.$store.getters['application/getAllOfWorkspace'](
        this.workspace
      ).map((application) => application.name)
      const baseName = this.applicationType.getDefaultName()
      return getNextAvailableNameInSequence(baseName, excludeNames)
    },
    async submitted(values) {
      this.loading = true
      this.hideError()

      try {
        const application = await this.$store.dispatch('application/create', {
          type: this.applicationType.type,
          workspace: this.workspace,
          values,
        })
        this.$emit('created', application)
        // select the application just created in the sidebar and open it
        await this.$store.dispatch('application/selectById', application.id)
        await this.$registry
          .get('application', application.type)
          .select(application, this)
        this.hide()
      } catch (error) {
        this.handleError(error, 'application')
      } finally {
        this.loading = false
      }
    },
    async handleOpenDatabase() {
      const application = this.$store.getters['application/get'](
        this.job.databaseId
      )
      const type = this.$registry.get('application', application.type)
      if (await type.select(application, this)) {
        this.hide()
        this.job.isRunning = false
        this.job.hasSucceeded = false
      }
    },
    handleSubmit() {
      this.$refs.applicationForm.submit()
    },
    handleJobDone(event) {
      this.job.hasSucceeded = true
      this.job.status = event.state
      this.job.progressPercentage = event.progress_percentage
      this.job.databaseId = event.databaseId
      this.job.isRunning = false
      this.loading = false
    },
    handleJobUpdated(event) {
      this.job.isRunning = true
      this.job.status = event.state
      this.job.progressPercentage = event.progress_percentage
    },
    handleHidden() {
      this.importType = null
      this.job.isRunning = false
      this.job.hasSucceeded = false
      this.job.status = ''
      this.job.progressPercentage = 0
      this.job.databaseId = null
    },
    handleJobFailed(event) {
      this.job.status = event.state
      this.job.isRunning = false
      this.loading = false
      this.job.hasSucceeded = false
    },
    handleAirtableSubmitted(event) {
      this.loading = true
    },
  },
}
</script>
