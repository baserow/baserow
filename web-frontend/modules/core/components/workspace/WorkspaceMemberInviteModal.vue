<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{ $t('membersSettings.membersInviteModal.title') }}
    </h2>
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
  </Modal>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import WorkspaceInviteForm from '@baserow/modules/core/components/workspace/WorkspaceInviteForm'
import CaptchaWidget from '@baserow/modules/core/components/auth/CaptchaWidget'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'

export default {
  name: 'MembersInviteModal',
  components: { WorkspaceInviteForm, CaptchaWidget },
  mixins: [modal, error],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  emits: ['invite-submitted'],
  data() {
    return {
      inviteLoading: false,
      captchaToken: '',
    }
  },
  methods: {
    show(...args) {
      this.hideError()
      // Captcha tokens are single use, so a token from a previous open could
      // already be consumed or expired.
      this.captchaToken = ''
      this.$refs.captchaWidget?.reset()
      return modal.methods.show.call(this, ...args)
    },
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
        this.$bus.$emit('invite-submitted', data)
        this.$emit('invite-submitted')
        this.hide()
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
            this.getTooManyInvitationsText(error)
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
    getTooManyInvitationsText(error) {
      const retryAfter = parseInt(error.response?.headers?.['retry-after'], 10)

      if (!retryAfter) {
        return this.$t(
          'membersSettings.membersInviteModal.errors.tooManyInvitations.text'
        )
      }

      return this.$t(
        'membersSettings.membersInviteModal.errors.tooManyInvitations.textWithWait',
        { wait: moment.duration(retryAfter, 'seconds').humanize() }
      )
    },
  },
}
</script>
