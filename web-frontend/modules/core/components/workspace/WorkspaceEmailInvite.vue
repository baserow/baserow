<template>
  <div>
    <Error :error="error"></Error>
    <WorkspaceInviteForm
      ref="inviteForm"
      :workspace="workspace"
      @submitted="inviteSubmitted"
    >
      <template #default>
        <CaptchaWidget
          ref="captchaWidget"
          class="col col-12 margin-top-2"
          context="workspace_invitation"
          @token="onCaptchaToken"
        />
        <div class="col col-12 align-right margin-top-2">
          <Button
            type="primary"
            :loading="inviteLoading"
            :disabled="inviteLoading"
          >
            {{ $t('membersSettings.membersInviteModal.submit') }}
          </Button>
        </div>
      </template>
      <template #roleSelectorLabel>
        <HelpIcon
          class="margin-right-1"
          :tooltip="$t('membersSettings.membersInviteModal.helpIconText')"
        />
      </template>
    </WorkspaceInviteForm>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import WorkspaceInviteForm from '@baserow/modules/core/components/workspace/WorkspaceInviteForm'
import CaptchaWidget from '@baserow/modules/core/components/auth/CaptchaWidget'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'

export default {
  name: 'WorkspaceEmailInvite',
  components: { WorkspaceInviteForm, CaptchaWidget },
  mixins: [error],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  emits: ['submitted'],
  data() {
    return {
      inviteLoading: false,
      captchaToken: '',
    }
  },
  methods: {
    reset() {
      this.hideError()
      this.captchaToken = ''
      this.$refs.captchaWidget?.reset()
    },
    /**
     * Send an email invitation after the selected workspace role has been validated.
     */
    async inviteSubmitted(values) {
      this.inviteLoading = true
      this.hideError()

      try {
        const acceptUrl = `${this.$config.public.baserowEmbeddedShareUrl}/workspace-invitation`
        const { data } = await WorkspaceService(this.$client).sendInvitation(
          this.workspace.id,
          acceptUrl,
          { ...values, captchaToken: this.captchaToken }
        )
        this.$bus.$emit('invite-submitted', data)
        this.$emit('submitted')
      } catch (error) {
        this.$refs.captchaWidget?.reset()
        if (error.handler?.isTooManyRequests()) {
          this.showError(
            this.$t(
              'membersSettings.membersInviteModal.errors.tooManyInvitations.title'
            ),
            this.$t(
              'membersSettings.membersInviteModal.errors.tooManyInvitations.text'
            )
          )
          error.handler.handled()
          this.inviteLoading = false
          return
        }

        this.handleError(error, 'workspace', {
          ERROR_GROUP_USER_ALREADY_EXISTS: new ResponseErrorMessage(
            this.$t(
              'membersSettings.membersInviteModal.errors.userAlreadyInWorkspace.title'
            ),
            this.$t(
              'membersSettings.membersInviteModal.errors.userAlreadyInWorkspace.text'
            )
          ),
          ERROR_CAPTCHA_VERIFICATION_FAILED: new ResponseErrorMessage(
            this.$t('error.captchaVerificationFailedTitle'),
            this.$t('error.captchaVerificationFailedMessage')
          ),
        })
      }

      this.inviteLoading = false
    },
    onCaptchaToken(token) {
      this.captchaToken = token
    },
  },
}
</script>
