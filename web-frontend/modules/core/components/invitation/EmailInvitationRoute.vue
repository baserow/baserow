<template>
  <div>
    <h2 class="box__title">{{ $t('inviteModal.emailTitle') }}</h2>
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
  name: 'EmailInvitationRoute',
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
    async inviteSubmitted(values) {
      this.inviteLoading = true
      this.hideError()

      try {
        // The public accept url is the page where the user can publicly navigate too,
        // to accept the workspace invitation.
        const acceptUrl = `${this.$config.public.baserowEmbeddedShareUrl}/workspace-invitation`
        const { data } = await WorkspaceService(this.$client).sendInvitation(
          this.workspace.id,
          acceptUrl,
          { ...values, captchaToken: this.captchaToken }
        )
        this.$emit('submitted', data)
      } catch (error) {
        // The captcha token can only be used once, so a new one must be solved
        // before the invitation can be sent again.
        if (this.$refs.captchaWidget) {
          this.$refs.captchaWidget.reset()
        }
        // The backend responds with a generic throttled error, so it can't be
        // matched on an error code like the ones below.
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
