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
        <img
          v-if="qr_code"
          :src="qr_code"
          alt="TOTP QR Code"
          class="enable-with-qr-code__step-qr-code"
        />
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
        <AuthCodeInput @all-filled="checkCode" />
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
      qr_code: null,
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
          'totp'
        )
        console.log({ data })
        this.qr_code = data.provisioning_qr_code
      } catch (error) {
        this.handleError(error)
      } finally {
        this.loading = false
      }
    },
    async checkCode(code) {
      // TODO: loading, error
      try {
        const params = { code }
        const { data } = await TwoFactorAuthService(this.$client).configure(
          'totp',
          params
        )
        const title = 'Successfully enabled two-factor authentication'
        this.$store.dispatch('toast/success', { title })
        this.$emit('verified', data.backup_codes)
      } catch (error) {
        // TODO: diff type of error?
        const title = 'Verification failed' // this.$t('generalSettings.cantUpdateApplicationTitle')
        this.$store.dispatch('toast/error', { title })
      } finally {
        // this.loading = false
      }
    },
  },
}
</script>
