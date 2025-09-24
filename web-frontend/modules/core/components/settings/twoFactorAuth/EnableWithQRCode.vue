<template>
  <div class="enable-with-qr-code">
    <div class="enable-with-qr-code__step">
      <div class="enable-with-qr-code__number">1</div>
      <div>
        <div class="enable-with-qr-code__step-heading">Scan QR code</div>
        <div class="enable-with-qr-code__step-description">
          Scan the code with an app like Google Authenticator, Authy or
          Microsoft Authenticator, or click here to copy the code.
        </div>
      </div>
    </div>
    <div class="enable-with-qr-code__step">
      <div class="enable-with-qr-code__number">2</div>
      <div>
        <div class="enable-with-qr-code__step-heading">
          Enter the code shown
        </div>
        <div class="enable-with-qr-code__step-description">
          Enter a 6-digit code shown by the app to confirm that you have set it
          up correctly.
        </div>
        <AuthCodeInput />
      </div>
    </div>
  </div>
</template>

<script>
import AuthCodeInput from '@baserow/modules/core/components/settings/twoFactorAuth/AuthCodeInput'
import TwoFactorAuthService from '@baserow/modules/core/services/twoFactorAuth'

export default {
  name: 'EnableWithQRCode',
  components: { AuthCodeInput },
  data() {
    return {
      loading: false,
    }
  },
  mounted() {
    this.configureTOTP()
  },
  methods: {
    async configureTOTP() {
      // TODO: loading, error
      this.loading = true

      try {
        const { data } = await TwoFactorAuthService(this.$client).configure(
          'totp',
          true
        )
        console.log({ data })
      } catch (error) {
        this.handleError(error)
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
