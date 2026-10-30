<template>
  <Modal
    ref="modal"
    class="user-template-modal-wrapper"
    :box-padding="false"
    :close-button="false"
    @hidden="$emit('hidden')"
  >
    <div class="user-template-modal">
      <div class="user-template-modal__head">
        <button
          v-if="step === 'content'"
          type="button"
          class="user-template-modal__head-action user-template-modal__back"
          :disabled="jobIsRunning || createLoading"
          @click="goToDetails"
        >
          <i class="iconoir-nav-arrow-left"></i>
        </button>
        <h2 class="user-template-modal__title">
          {{
            step === 'details'
              ? $t('createUserTemplateModal.detailsTitle')
              : $t('createUserTemplateModal.contentTitle')
          }}
        </h2>
        <button
          type="button"
          class="user-template-modal__head-action user-template-modal__close"
          :title="$t('action.close')"
          @click="hide()"
        >
          <i class="iconoir-cancel"></i>
        </button>
      </div>

      <template v-if="step === 'details'">
        <div class="user-template-modal__body">
          <p class="user-template-modal__description">
            {{ $t('createUserTemplateModal.detailsDescription') }}
          </p>
          <UserTemplateDetailsForm
            ref="detailsForm"
            :model-value="details"
            :categories="categories"
            :show-errors="detailsSubmitted"
            @update:model-value="Object.assign(values, $event)"
          />
          <UserTemplateVisibilityForm
            :model-value="visibility"
            :needs-review="requireApproval"
            class="margin-top-2"
            @update:model-value="Object.assign(values, $event)"
          />
        </div>

        <div class="user-template-modal__footer">
          <div class="user-template-modal__footer-actions">
            <Button type="secondary" @click="hide()">
              {{ $t('action.cancel') }}
            </Button>
            <Button
              type="primary"
              :disabled="!visibilityValid"
              @click="goToContent"
            >
              {{ $t('createUserTemplateModal.continue') }}
            </Button>
          </div>
        </div>
      </template>

      <!-- The content form stays mounted between the steps, so that it loads the
      permissions and keeps the chosen workspace once per opening. -->
      <div v-show="step === 'content'" class="user-template-modal__body">
        <p class="user-template-modal__description">
          {{ $t('createUserTemplateModal.contentDescription') }}
        </p>

        <UserTemplateContentForm
          :model-value="content"
          :disabled="jobIsRunning || createLoading"
          @update:model-value="Object.assign(values, $event)"
          @update:valid="contentValid = $event"
        />

        <Error :error="error" class="margin-bottom-0"></Error>
      </div>

      <template v-if="step === 'content'">
        <div class="user-template-modal__footer">
          <div
            v-if="jobIsRunning || jobIsFinished"
            class="user-template-modal__progress"
          >
            <ProgressBar
              :value="job.progress_percentage"
              :status="jobHumanReadableState"
            />
          </div>
          <div v-else class="user-template-modal__selected">
            {{
              $t('userTemplateContentForm.selectedApplications', {
                count: values.applicationIds.length,
              })
            }}
          </div>
          <div class="user-template-modal__footer-actions">
            <ButtonText
              v-if="jobIsRunning || cancelLoading"
              tag="a"
              type="secondary"
              class="modal-progress__cancel-button"
              :loading="cancelLoading"
              @click="cancelJob"
            >
              {{ $t('action.cancel') }}
            </ButtonText>
            <Button v-else type="secondary" @click="hide()">
              {{ $t('action.cancel') }}
            </Button>
            <Button
              type="primary"
              :loading="createLoading || jobIsRunning || jobIsFinished"
              :disabled="!canCreate"
              @click="create"
            >
              {{ $t('createUserTemplateModal.create') }}
            </Button>
          </div>
        </div>
      </template>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import job from '@baserow/modules/core/mixins/job'
import JobService from '@baserow/modules/core/services/job'
import { CreateUserTemplateJobType } from '@baserow/modules/core/jobTypes'
import { DEFAULT_TEMPLATE_ICON } from '@baserow/modules/core/utils/templateIcons'
import UserTemplateContentForm from '@baserow/modules/core/components/template/UserTemplateContentForm'
import UserTemplateDetailsForm from '@baserow/modules/core/components/template/UserTemplateDetailsForm'
import UserTemplateVisibilityForm from '@baserow/modules/core/components/template/UserTemplateVisibilityForm'

export default {
  name: 'CreateUserTemplateModal',
  components: {
    UserTemplateContentForm,
    UserTemplateDetailsForm,
    UserTemplateVisibilityForm,
  },
  mixins: [modal, error, job],
  props: {
    // The categories an author can pick from, each with an `id` and a `name`. An
    // instance that never synced the templates has none, and then none is needed.
    categories: {
      type: Array,
      required: true,
    },
  },
  emits: ['created', 'hidden'],
  data() {
    return {
      step: 'details',
      // The errors of the details step show after the first attempt to continue.
      detailsSubmitted: false,
      createLoading: false,
      // Whether the content form allows to create the template.
      contentValid: false,
      values: this.getDefaultValues(),
    }
  },
  computed: {
    details() {
      const { icon, name, description, categoryIds } = this.values
      return { icon, name, description, categoryIds }
    },
    content() {
      const { workspaceId, applicationIds } = this.values
      return { workspaceId, applicationIds }
    },
    visibility() {
      const { makePublic, publicListingConsent } = this.values
      return { makePublic, publicListingConsent }
    },
    // A new template made public goes to an instance admin's review first.
    requireApproval() {
      return Boolean(
        this.$store.getters['settings/get'].user_templates_require_approval
      )
    },
    // Public only once the author agreed to be listed.
    visibilityValid() {
      return !this.values.makePublic || this.values.publicListingConsent
    },
    canCreate() {
      return (
        this.contentValid &&
        !this.createLoading &&
        !this.jobIsRunning &&
        !this.jobIsFinished
      )
    },
  },
  methods: {
    show(...args) {
      // A running job is shown again instead of an empty form, also one started
      // from another wizard. A job that failed while the modal was closed is shown
      // once with its error and inputs. A template still being sent keeps its
      // inputs.
      const runningJob = this.findRunningJob()
      if (runningJob && runningJob.id !== this.job?.id) {
        this.reset()
        this.restoreJob(runningJob)
      } else if (this.job?.state === 'failed') {
        this.job = null
      } else if (!this.jobIsRunning && !this.createLoading) {
        this.reset()
      }
      modal.methods.show.call(this, ...args)
    },
    getDefaultValues() {
      return {
        icon: DEFAULT_TEMPLATE_ICON,
        name: '',
        description: '',
        categoryIds: [],
        // The content form selects a workspace when it's shown.
        workspaceId: null,
        applicationIds: [],
        makePublic: false,
        publicListingConsent: false,
      }
    },
    reset() {
      this.step = 'details'
      this.detailsSubmitted = false
      this.createLoading = false
      this.contentValid = false
      this.job = null
      this.values = this.getDefaultValues()
      this.hideError()
    },
    findRunningJob() {
      // A job with a template from the start updates that template.
      return this.$store.getters['job/getUnfinishedJobs'].find(
        (job) =>
          job.type === CreateUserTemplateJobType.getType() && !job.template
      )
    },
    restoreJob(runningJob) {
      this.job = runningJob
      this.step = 'content'
      this.values = {
        icon: runningJob.icon,
        name: runningJob.name,
        description: runningJob.description,
        categoryIds: [...runningJob.category_ids],
        workspaceId: runningJob.workspace_id,
        applicationIds: [...runningJob.application_ids],
        makePublic: runningJob.make_public,
        publicListingConsent: runningJob.make_public,
      }
    },
    goToContent() {
      this.detailsSubmitted = true
      if (!this.$refs.detailsForm.isValid() || !this.visibilityValid) {
        return
      }
      this.step = 'content'
    },
    goToDetails() {
      this.hideError()
      this.step = 'details'
    },
    async create() {
      if (!this.canCreate) {
        return
      }
      this.createLoading = true
      this.hideError()
      try {
        const { data } = await JobService(this.$client).create(
          CreateUserTemplateJobType.getType(),
          {
            workspace_id: this.values.workspaceId,
            application_ids: this.values.applicationIds,
            name: this.values.name.trim(),
            description: this.values.description,
            icon: this.values.icon,
            category_ids: this.values.categoryIds,
            make_public: this.values.makePublic,
            public_listing_consent: this.values.publicListingConsent,
          }
        )
        await this.createAndMonitorJob(data)
      } catch (error) {
        this.handleError(error)
      } finally {
        this.createLoading = false
      }
    },
    onJobFinished() {
      this.$emit('created', this.job)
      this.hide()
      this.reset()
    },
    onJobFailed() {
      if (this.job.revision) {
        // It failed after the template was created, which is kept. It's handled
        // as created, so that the author doesn't create it again. Then making it
        // public is what failed, if that was asked.
        this.$store.dispatch('toast/warning', {
          title: this.job.make_public
            ? this.$t('createUserTemplateModal.failedPublicAfterCreated')
            : this.$t('createUserTemplateModal.failedAfterCreated'),
        })
        this.onJobFinished()
        return
      }
      this.showError(
        this.$t('clientHandler.notCompletedTitle'),
        this.job.human_readable_error
      )
    },
    onJobCancelled() {
      // The inputs are kept, so that the author can try again.
      this.job = null
    },
    getCustomHumanReadableJobState() {
      return ''
    },
    getJobNotCancellableMessage() {
      return this.$t('createUserTemplateModal.cannotBeCancelled')
    },
  },
}
</script>
