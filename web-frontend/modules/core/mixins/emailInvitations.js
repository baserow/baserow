import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'

// How long the captcha widget gets to issue a fresh token between two
// invitations before the next one is sent without.
const CAPTCHA_TOKEN_TIMEOUT = 30000

/**
 * Shared by the invitation routes that send email invitations through their
 * target type, one request per address. A captcha token is accepted once, so
 * with a captcha in place the widget solves a new token between two addresses
 * and the next invitation waits for it. The component needs the `workspace`,
 * `target` and `targetType` props, a `captchaWidget` ref whose `token` event
 * calls `onCaptchaToken`, and the error mixin for `handleInvitationError`.
 */
export default {
  data() {
    return {
      captchaToken: '',
      captchaTokenWaiter: null,
    }
  },
  methods: {
    onCaptchaToken(token) {
      this.captchaToken = token
      if (token && this.captchaTokenWaiter) {
        const waiter = this.captchaTokenWaiter
        this.captchaTokenWaiter = null
        waiter(token)
      }
    },
    /**
     * The captcha token to send with the next invitation: the one the widget
     * holds, or else the next one it issues. Without a captcha requirement there
     * is nothing to wait for. If the widget doesn't come up with a token in time
     * the request goes out without one, and the backend's captcha error tells
     * the user to try again.
     */
    nextCaptchaToken() {
      if (!this.$refs.captchaWidget?.captchaEnabled || this.captchaToken) {
        return Promise.resolve(this.captchaToken)
      }
      return new Promise((resolve) => {
        const timeout = setTimeout(() => {
          this.captchaTokenWaiter = null
          resolve('')
        }, CAPTCHA_TOKEN_TIMEOUT)
        this.captchaTokenWaiter = (token) => {
          clearTimeout(timeout)
          resolve(token)
        }
      })
    },
    /**
     * Sends one invitation per picked address with the given role, in order,
     * and calls `onSent` with the pick and the created invitation after each
     * one, so that the caller can take the pick out of its input right away.
     * Stops at the first failure and leaves it to the caller to handle.
     */
    async sendInvitations(picks, roleUid, onSent) {
      for (const pick of picks) {
        const captchaToken = await this.nextCaptchaToken()
        const invitation = await this.targetType.sendInvitation(
          this.workspace,
          this.target,
          { email: pick.email, permissions: roleUid, captchaToken }
        )
        // The token was used up by this request, the widget solves a new one
        // for the next address.
        this.$refs.captchaWidget?.reset()
        onSent(pick, invitation)
      }
    },
    /**
     * Shows why inviting failed, with the invitation specific messages for the
     * errors a user can run into.
     */
    handleInvitationError(error) {
      this.$refs.captchaWidget?.reset()
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
    },
  },
}
