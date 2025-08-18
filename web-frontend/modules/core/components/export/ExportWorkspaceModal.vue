<template>
  <Modal>
    <h2 class="box__title">
      {{ $t('exportWorkspaceModal.title') }} {{ workspace.name }}
    </h2>
    <p>
      {{ $t('exportWorkspaceModal.description') }}
    </p>
    <component
      :is="component"
      v-for="(component, index) in workspaceExportModalAlertComponents"
      :key="index"
    ></component>
    <Error :error="error"></Error>
    <div>
      <ExportWorkspaceForm
        ref="form"
        :workspace="workspace"
        :disabled="jobIsRunning"
        @submitted="submitted"
        @update="updateSelectedApplications"
      />

      <!-- Export button section -->
      <div
        class="export-workspace__button-section"
        :class="{
          'export-workspace__button-section--with-progress':
            jobIsRunning || jobIsFinished,
        }"
      >
        <div
          v-if="jobIsRunning || jobIsFinished"
          class="export-workspace__progress"
        >
          <ProgressBar
            :value="job.progress_percentage"
            :status="jobHumanReadableState"
          />
        </div>
        <Button
          v-if="!createFinished"
          size="large"
          :loading="createLoading"
          :disabled="
            createLoading || exportJobLoading || !hasSelectedApplications
          "
          @click="submitForm"
        >
          {{ $t('exportWorkspaceModal.export') }}
        </Button>
        <Button v-else type="secondary" tag="a" size="large" @click="reset()">
          {{ $t('exportWorkspaceModal.reset') }}
        </Button>
      </div>
      <div class="export-workspace__list">
        <div
          v-if="exportJobLoading"
          class="loading export-workspace__list--loading"
        ></div>
        <div v-else-if="exportJobs.length > 0">
          <ExportWorkspaceListItem
            v-for="job in exportJobs"
            ref="exportsList"
            :key="job.id"
            :export-job="job"
            :workspace="workspace"
            :last-updated="job.created_on"
          ></ExportWorkspaceListItem>
        </div>
        <div v-else>
          {{ $t('exportWorkspaceModal.noExports') }}
        </div>
      </div>
    </div>
    <template #actions> </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import ExportWorkspaceService from '@baserow/modules/core/services/importExportService'
import job from '@baserow/modules/core/mixins/job'
import ExportWorkspaceForm from '@baserow/modules/core/components/export/ExportWorkspaceForm'
import { ExportApplicationsJobType } from '@baserow/modules/core/jobTypes'
import ExportWorkspaceListItem from '@baserow/modules/core/components/export/ExportWorkspaceListItem.vue'
import {
  EXPORT_SERIALIZED_EXPORTING,
  EXPORT_SERIALIZED_EXPORTING_TABLE,
  EXPORT_WORKSPACE_CREATE_ARCHIVE,
} from '@baserow/modules/core/constants'

const WORKSPACE_EXPORTS_LIMIT = 5

export default {
  name: 'ExportWorkspaceModal',
  components: {
    ExportWorkspaceForm,
    ExportWorkspaceListItem,
  },
  mixins: [modal, error, job],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      createLoading: false,
      createFinished: false,
      exportJobLoading: false,
      exportJobs: [],
      selectedApplicationIds: [],
    }
  },
  computed: {
    workspaceExportModalAlertComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .map((plugin) =>
          plugin.getExtraExportWorkspaceModalComponents(this.workspace)
        )
        .filter((component) => component !== null)
    },
    hasSelectedApplications() {
      return this.selectedApplicationIds.length > 0
    },
  },
  methods: {
    show(...args) {
      this.reset()
      this.loadExports()
      modal.methods.show.bind(this)(...args)
    },
    submitForm() {
      this.$refs.form.submit()
    },
    updateSelectedApplications(applicationIds) {
      this.selectedApplicationIds = [...applicationIds]
    },
    async submitted(values) {
      this.createLoading = true
      this.hideError()
      try {
        const { data: job } = await ExportWorkspaceService(
          this.$client
        ).exportApplications(this.workspace.id, values)
        await this.createAndMonitorJob(job)
      } catch (error) {
        this.createLoading = false
        this.handleError(error)
      }
    },

    onJobFinished() {
      this.createLoading = false
      this.createFinished = true
      if (
        this.job.type === ExportApplicationsJobType.getType() &&
        this.job.workspace_id === this.workspace.id
      ) {
        this.exportJobs.unshift(this.job)
        this.exportJobs = this.exportJobs.splice(0, WORKSPACE_EXPORTS_LIMIT)
      }
    },

    // eslint-disable-next-line require-await
    async onJobFailed() {
      this.createLoading = false
      this.showError(
        this.$t('clientHandler.notCompletedTitle'),
        this.job.human_readable_error
      )
    },
    async loadExports() {
      this.exportJobLoading = true

      try {
        const { data: exportJobs } = await ExportWorkspaceService(
          this.$client
        ).listExports(this.workspace.id)
        this.exportJobs = exportJobs?.results || []
      } catch (error) {
        this.handleError(error)
      } finally {
        this.exportJobLoading = false
      }
      this.loadRunningJob()
    },
    loadRunningJob() {
      const runningJob = this.$store.getters['job/getUnfinishedJobs'].find(
        (job) => {
          return (
            job.type === ExportApplicationsJobType.getType() &&
            job.workspace_id === this.workspace.id
          )
        }
      )
      if (runningJob) {
        this.job = runningJob
        this.createLoading = true
      }
    },
    reset() {
      this.job = null
      this.createFinished = false
      this.createLoading = false
      this.hideError()
    },

    getCustomHumanReadableJobState(jobState) {
      if (jobState.startsWith(EXPORT_SERIALIZED_EXPORTING_TABLE)) {
        return this.$t('exportWorkspaceModal.exportingTableState', {
          table: jobState.replace(EXPORT_SERIALIZED_EXPORTING_TABLE, ''),
        })
      }
      if (jobState === EXPORT_WORKSPACE_CREATE_ARCHIVE) {
        return this.$t('exportWorkspaceModal.exportingCreateArchiveState')
      }
      if (jobState === EXPORT_SERIALIZED_EXPORTING) {
        return this.$t('exportWorkspaceModal.exportingState')
      }
      return ''
    },
  },
}
</script>
