<template>
  <Modal :full-screen="false" :close-button="true">
    <h2 class="box__title">
      {{ $t('importWorkspaceModal.title') }}
    </h2>
    <p>
      {{ $t('importWorkspaceModal.description') }}
    </p>
    <component
      :is="component"
      v-for="(component, index) in workspaceImportModalAlertComponents"
      :key="index"
    ></component>
    <Error :error="error"></Error>
    <div class="import-workspace-modal">
      <div v-if="currentStage === STAGES.UPLOAD">
        <UploadFileDropzone
          v-if="!importFile"
          :multiple-files="false"
          :file-types-acceptable="fileTypesAcceptable"
          @input="addFile($event)"
        />
        <SelectedFileDetails
          v-else
          :import-file="importFile"
          :workspace-id="workspace.id"
          @import-workspace-reset="reset"
        />

        <div class="align-right">
          <div v-if="uploading" class="upload-files__progress">
            <ProgressBar :value="percentage" :show-value="true" />
          </div>
          <Button
            type="primary"
            size="large"
            :loading="uploading"
            :disabled="uploading || !importFile"
            @click="process()"
          >
            <template v-if="!uploading && hasFailed">{{
              $t('uploadFileUserFileUpload.retry')
            }}</template>
            <template v-else>{{ $t('importWorkspaceModal.upload') }}</template>
          </Button>
        </div>
      </div>
      <div v-else-if="currentStage === STAGES.IMPORT">
        <SelectedFileDetails
          :import-file="importFile"
          :resource-id="resourceId"
          :workspace-id="workspace.id"
          @import-workspace-reset="reset"
        >
        </SelectedFileDetails>
        <ImportWorkspaceForm ref="form" @submitted="importWorkspace">
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
              v-if="currentStage !== STAGES.DONE"
              size="large"
              :loading="importing"
              :disabled="importing"
            >
              {{ $t('importWorkspaceModal.import') }}
            </Button>
          </template>
        </ImportWorkspaceForm>
      </div>
    </div>
  </Modal>
</template>

<script>
import UploadFileDropzone from '@baserow/modules/core/components/files/UploadFileDropzone.vue'
import SelectedFileDetails from '@baserow/modules/core/components/import/SelectedFileDetails.vue'
import { getFilesFromEvent } from '@baserow/modules/core/utils/file'
import ImportWorkspaceService from '@baserow/modules/core/services/importWorkspaceService'
import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'
import job from '@baserow/modules/core/mixins/job'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import ImportWorkspaceForm from '@baserow/modules/core/components/import/ImportWorkspaceForm.vue'
import { notifyIf } from '@baserow/modules/core/utils/error'

const STAGES = {
  UPLOAD: 'upload',
  IMPORT: 'import',
  DONE: 'done',
  FAILED: 'failed',
}

export default {
  name: 'ImportWorkspace',
  components: { UploadFileDropzone, SelectedFileDetails, ImportWorkspaceForm },
  mixins: [modal, error, job],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      fileTypesAcceptable: ['application/zip'],
      importFile: null,
      uploading: false,
      importing: false,
      hasFailed: false,
      resourceId: null,
      percentage: 0,
      iconClass: '',
      currentStage: STAGES.UPLOAD,
      STAGES,
    }
  },
  computed: {
    workspaceImportModalAlertComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .map((plugin) =>
          plugin.getExtraImportWorkspaceModalComponents(this.workspace)
        )
        .filter((component) => component !== null)
    },
    importButtonLabel() {
      return this.currentStage === STAGES.DONE
        ? this.$t('importWorkspaceModal.close')
        : this.$t('importWorkspaceModal.import')
    },
  },
  methods: {
    show(...args) {
      this.hideError()
      if (
        this.currentStage !== STAGES.UPLOAD ||
        this.currentStage !== STAGES.IMPORT
      ) {
        this.reset()
      }
      modal.methods.show.bind(this)(...args)
    },
    addFile(event) {
      const files = getFilesFromEvent(event)
      if (files.length > 0) {
        this.importFile = files[0]
      }
    },

    async process() {
      await this.upload()
      await this.importWorkspace()
    },

    async upload() {
      this.uploading = true
      this.iconClass = mimetype2icon(this.importFile.type)

      const progress = (event) => {
        this.percentage = Math.round((event.loaded * 100) / event.total)
      }
      try {
        const { data } = await ImportWorkspaceService(this.$client).uploadFile(
          this.workspace.id,
          this.importFile,
          progress
        )
        this.resourceId = data.id
        this.currentStage = STAGES.IMPORT
      } catch (error) {
        const message = error.handler.getMessage('userFile')
        error.handler.handled()
        this.error = message.message
        this.currentStage = STAGES.FAILED
      } finally {
        this.uploading = false
      }
    },

    async onJobFinished() {
      this.importing = false
      this.currentStage = STAGES.DONE

      const installedApplications = this.job.installed_applications
      try {
        for (const application of installedApplications) {
          await this.$store.dispatch('application/forceCreate', application)
        }
        this.$store.dispatch('toast/info', {
          title: this.$i18n.t('importWorkspaceModal.successTitle'),
          message: this.$i18n.t('importWorkspaceModal.successMessage', {
            count: installedApplications.length,
          }),
        })
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.close()
      }
    },

    // eslint-disable-next-line require-await
    async onJobFailed() {
      this.currentStage = STAGES.FAILED
      this.importing = false
      this.showError(
        this.$t('clientHandler.notCompletedTitle'),
        this.job.human_readable_error
      )
    },

    reset() {
      this.importFile = null
      this.currentStage = STAGES.UPLOAD
      this.resourceId = null
    },

    close() {
      this.reset()
      this.hide()
    },

    async importWorkspace() {
      this.importing = true
      this.hideError()
      try {
        const { data: job } = await ImportWorkspaceService(
          this.$client
        ).triggerImport(this.workspace.id, this.resourceId)
        this.job = job
        await this.createAndMonitorJob(job)
      } catch (error) {
        this.createLoading = false
        this.handleError(error)
      }
    },
  },
}
</script>
