<template>
  <Modal :full-screen="false" :close-button="true">
    <h2 class="box__title">
      {{ $t('importWorkspaceModal.title') }}
    </h2>
    <p>
      {{ $t('importWorkspaceModal.description') }}
      <template v-if="signatureCheckEnabled">
        {{ $t('importWorkspaceModal.signatureVerificationNote') }}
      </template>
    </p>
    <component
      :is="component"
      v-for="(component, index) in workspaceImportModalAlertComponents"
      :key="index"
    ></component>
    <Error :error="error"></Error>
    <div>
      <div v-if="currentStage === STAGES.UPLOAD">
        <UploadFileDropzone
          v-if="!importFile"
          :multiple-files="false"
          :file-types-acceptable="fileTypesAcceptable"
          @input="addFile($event)"
        />
        <div v-else>
          <SelectedFileDetails
            :import-file="importFile"
            :workspace-id="workspace.id"
            @import-workspace-reset="reset"
          />

          <div
            v-if="applicationGroups.length > 0"
            class="import-workspace__application-selection"
          >
            <ImportApplicationSelector
              :application-groups="applicationGroups"
              :selected-application-ids="selectedApplicationIds"
              @update="updateSelectedApplications"
            />
          </div>
        </div>

        <div
          class="import-workspace__button-section"
          :class="{
            'import-workspace__button-section--with-progress': uploading,
          }"
        >
          <div v-if="uploading" class="import-workspace__progress">
            <ProgressBar
              :value="percentage"
              :status="$t('importWorkspaceModal.uploading')"
            />
          </div>
          <Button
            type="primary"
            size="large"
            :loading="uploading"
            :disabled="isUploadDisabled"
            @click="process()"
          >
            <template v-if="!uploading && hasFailed">{{
              $t('uploadFileUserFileUpload.retry')
            }}</template>
            <template v-else>{{
              $t('importWorkspaceModal.uploadAndImport')
            }}</template>
          </Button>
        </div>
      </div>
      <div v-else-if="currentStage === STAGES.IMPORT && importFile">
        <SelectedFileDetails
          :import-file="importFile"
          :resource-id="resourceId"
          :workspace-id="workspace.id"
          :disabled="importing"
          @import-workspace-reset="reset"
        >
        </SelectedFileDetails>

        <div
          v-if="applicationGroups.length > 0"
          class="import-workspace__application-selection"
        >
          <ImportApplicationSelector
            :application-groups="applicationGroups"
            :selected-application-ids="selectedApplicationIds"
            :disabled="importing"
            @update="updateSelectedApplications"
          />
        </div>

        <ImportWorkspaceForm ref="form" @submitted="importWorkspace" />

        <div
          class="import-workspace__button-section"
          :class="{
            'import-workspace__button-section--with-progress':
              jobIsRunning || jobIsFinished,
          }"
        >
          <div
            v-if="jobIsRunning || jobIsFinished"
            class="import-workspace__progress"
          >
            <ProgressBar
              :value="job?.progress_percentage || 0"
              :status="jobHumanReadableState"
            />
          </div>
          <Button
            v-if="currentStage !== STAGES.DONE"
            size="large"
            :loading="importing"
            :disabled="importing"
            @click="submitForm"
          >
            {{ $t('importWorkspaceModal.import') }}
          </Button>
        </div>
      </div>
    </div>
  </Modal>
</template>

<script>
import UploadFileDropzone from '@baserow/modules/core/components/files/UploadFileDropzone.vue'
import SelectedFileDetails from '@baserow/modules/core/components/import/SelectedFileDetails.vue'
import { getFilesFromEvent } from '@baserow/modules/core/utils/file'
import ImportWorkspaceService from '@baserow/modules/core/services/importExportService'
import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'
import job from '@baserow/modules/core/mixins/job'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import ImportWorkspaceForm from '@baserow/modules/core/components/import/ImportWorkspaceForm.vue'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { ImportApplicationsJobType } from '@baserow/modules/core/jobTypes'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import {
  IMPORT_SERIALIZED_IMPORTING,
  IMPORT_SERIALIZED_IMPORTING_TABLE_STRUCTURE,
  IMPORT_SERIALIZED_IMPORTING_TABLE_DATA,
} from '@baserow/modules/core/constants'
import ImportApplicationSelector from '@baserow/modules/core/components/import/ImportApplicationSelector.vue'
import {
  convertManifestToApplicationGroups,
  extractManifestFromZip,
} from '@baserow/modules/core/utils/zipManifest'

const STAGES = {
  UPLOAD: 'upload',
  IMPORT: 'import',
  DONE: 'done',
  FAILED: 'failed',
}

export default {
  name: 'ImportWorkspace',
  components: {
    UploadFileDropzone,
    SelectedFileDetails,
    ImportWorkspaceForm,
    ImportApplicationSelector,
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
      applicationGroups: [],
      selectedApplicationIds: [],
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
    signatureCheckEnabled() {
      return this.$store.getters['settings/get'].verify_import_signature
    },
    isUploadDisabled() {
      const noSelectionWhenShown =
        this.applicationGroups.length > 0 &&
        this.selectedApplicationIds.length === 0
      return this.uploading || !this.importFile || noSelectionWhenShown
    },
  },
  watch: {
    'workspace.id'() {
      this.hideError()
      this.reset()
    },
  },
  methods: {
    submitForm() {
      this.$refs.form.submit()
    },
    show(...args) {
      this.hideError()
      this.checkPendingImport()
      modal.methods.show.bind(this)(...args)
    },
    async addFile(event) {
      const files = getFilesFromEvent(event)
      if (files.length > 0) {
        this.importFile = files[0]
        await this.extractManifestFromFile()
      }
    },

    async process() {
      if (
        this.applicationGroups.length > 0 &&
        this.selectedApplicationIds.length > 0
      ) {
        await this.upload()
        if (this.currentStage === STAGES.IMPORT) {
          await this.importWorkspace()
        }
      } else {
        await this.upload()
        if (this.currentStage === STAGES.IMPORT) {
          await this.importWorkspace()
        }
      }
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
        this.handleError(error, 'import_export', {
          ERROR_RESOURCE_IS_INVALID: new ResponseErrorMessage(
            this.$t('importWorkspaceModal.invalidResourceTitle'),
            this.$t('importWorkspaceModal.invalidResourceMessage')
          ),
          ERROR_UNTRUSTED_PUBLIC_KEY: new ResponseErrorMessage(
            this.$t('importWorkspaceModal.untrustedPublicKeyTitle'),
            this.$t('importWorkspaceModal.untrustedPublicKeyMessage')
          ),
        })
      } finally {
        this.uploading = false
        this.percentage = 0
      }
    },

    async extractManifestFromFile() {
      try {
        const manifest = await extractManifestFromZip(this.importFile)
        this.applicationGroups = convertManifestToApplicationGroups(manifest)

        this.selectedApplicationIds = this.applicationGroups
          .flatMap((group) => group.applications)
          .map((app) => app.id)
      } catch (error) {
        this.applicationGroups = []
        this.selectedApplicationIds = []

        this.$store.dispatch('toast/error', {
          title: 'Could not read ZIP file',
          message:
            error.message ||
            'The ZIP file does not contain a valid manifest.json file.',
        })
      }
    },

    updateSelectedApplications(selectedApplicationIds) {
      this.selectedApplicationIds = selectedApplicationIds
    },

    checkPendingImport() {
      const runningJob = this.$store.getters['job/getUnfinishedJobs'].find(
        (job) => {
          return (
            job.type === ImportApplicationsJobType.getType() &&
            job.workspace_id === this.workspace.id
          )
        }
      )
      if (runningJob) {
        this.importFile = runningJob.resource
        this.currentStage = STAGES.IMPORT
        this.job = runningJob
        this.importing = true
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
      this.hideError()
      this.applicationGroups = []
      this.selectedApplicationIds = []
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
        ).triggerImport(
          this.workspace.id,
          this.resourceId,
          this.selectedApplicationIds
        )
        await this.createAndMonitorJob(job)
      } catch (error) {
        this.importing = false
        this.handleError(error)
      }
    },

    getCustomHumanReadableJobState(jobState) {
      if (jobState.startsWith(IMPORT_SERIALIZED_IMPORTING_TABLE_STRUCTURE)) {
        return this.$t('importWorkspaceModal.importingTableStructure', {
          table: jobState.replace(
            IMPORT_SERIALIZED_IMPORTING_TABLE_STRUCTURE,
            ''
          ),
        })
      }
      if (jobState.startsWith(IMPORT_SERIALIZED_IMPORTING_TABLE_DATA)) {
        return this.$t('importWorkspaceModal.importingTableData', {
          table: jobState.replace(IMPORT_SERIALIZED_IMPORTING_TABLE_DATA, ''),
        })
      }
      if (jobState.startsWith(IMPORT_SERIALIZED_IMPORTING)) {
        return this.$t('importWorkspaceModal.importingState')
      }
      return ''
    },

    async extractApplications() {
      this.importing = true
      this.hideError()
      try {
        const { data } = await ImportWorkspaceService(
          this.$client
        ).extractApplications(this.workspace.id, this.importFile.id)
        this.applicationGroups = data.application_groups
        this.selectedApplicationIds = data.selected_application_ids
      } catch (error) {
        this.handleError(error, 'import_export', {
          ERROR_RESOURCE_IS_INVALID: new ResponseErrorMessage(
            this.$t('importWorkspaceModal.invalidResourceTitle'),
            this.$t('importWorkspaceModal.invalidResourceMessage')
          ),
          ERROR_UNTRUSTED_PUBLIC_KEY: new ResponseErrorMessage(
            this.$t('importWorkspaceModal.untrustedPublicKeyTitle'),
            this.$t('importWorkspaceModal.untrustedPublicKeyMessage')
          ),
        })
      } finally {
        this.importing = false
      }
    },
  },
}
</script>
