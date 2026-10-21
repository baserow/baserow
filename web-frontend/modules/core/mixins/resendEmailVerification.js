import AuthService from '@baserow/modules/core/services/auth'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  data() {
    return {
      resendLoading: false,
      resendSuccess: false,
    }
  },
  methods: {
    async resend(email) {
      if (this.resendLoading) {
        return
      }

      this.resendLoading = true

      try {
        await AuthService(this.$client).sendVerifyEmail(email)
        this.resendSuccess = true
        this.$store.dispatch('toast/info', {
          title: this.$t('resendEmailVerification.confirmationEmailSentTitle'),
          message: this.$t(
            'resendEmailVerification.confirmationEmailSentDescription'
          ),
        })
      } catch (error) {
        // The backend responds with a generic throttled error, which notifyIf
        // ignores because it has no error code.
        if (error.handler?.isTooManyRequests()) {
          const message = error.handler.getMessage()
          this.$store.dispatch('toast/error', {
            title: message.title,
            message: message.message,
          })
          error.handler.handled()
        } else {
          notifyIf(error, 'emailVerification')
        }
      }

      this.resendLoading = false
    },
  },
}
