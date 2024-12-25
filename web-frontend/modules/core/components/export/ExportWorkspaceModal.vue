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
      <h4 class="margin-bottom-2">
        {{ $t('exportWorkspaceForm.exportSettingsLabel') }}
      </h4>
      <ExportWorkspaceForm ref="form" @submitted="submitted">
        <template v-if="jobIsRunning || jobIsFinished" #select-applications>
          <div class="margin-right-2">
            <ProgressBar
              :value="job.progress_percentage"
              :status="jobHumanReadableState"
            />
          </div>
        </template>
        <template #default>
          <Button
            v-if="!createFinished"
            size="large"
            :loading="createLoading"
            :disabled="createLoading || exportJobLoading"
          >
            {{ $t('exportWorkspaceModal.export') }}
          </Button>
          <Button v-else type="secondary" tag="a" size="large" @click="reset()">
            {{ $t('exportWorkspaceModal.reset') }}
          </Button>
        </template>
      </ExportWorkspaceForm>
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
  },
  methods: {
    show(...args) {
      this.reset()
      this.loadExports()
      modal.methods.show.bind(this)(...args)
    },
    async submitted(values) {
      this.createLoading = true
      this.hideError()
      try {
        const { data: job } = await ExportWorkspaceService(
          this.$client
        ).exportApplications(this.workspace.id, values)
        this.job = job
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
      if (jobState.startsWith('importing')) {
        return this.$t('exportWorkspaceModal.importingState')
      }
      return ''
    },
  },
}
</script>
