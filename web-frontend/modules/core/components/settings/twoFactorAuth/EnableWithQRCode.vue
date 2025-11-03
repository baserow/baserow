<template>
  <div class="enable-with-qr-code">
    <div class="enable-with-qr-code__step">
      <div class="enable-with-qr-code__number">1</div>
      <div>
        <div class="enable-with-qr-code__step-heading">
          {{ $t('enableWithQRCode.scanQRCode') }}
        </div>
        <div class="enable-with-qr-code__step-description">
          {{ $t('enableWithQRCode.scanQRCodeDescription') }}
        </div>
        <div v-if="loading" class="loading-spinner" />
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
          {{ $t('enableWithQRCode.enterCode') }}
        </div>
        <div class="enable-with-qr-code__step-description">
          {{ $t('enableWithQRCode.enterCodeDescription') }}
        </div>
        <AuthCodeInput
          ref="authCodeInput"
          :class="{ 'loading-spinner': checkCodeLoading }"
          @all-filled="checkCode"
        />
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
      checkCodeLoading: false,
      qr_code: null,
    }
  },
  mounted() {
    this.configureTOTP()
  },
  methods: {
    async configureTOTP() {
      this.loading = true
      try {
        const { data } = await TwoFactorAuthService(this.$client).configure(
          'totp'
        )
        this.qr_code = data.provisioning_qr_code
      } catch (error) {
        const title = this.$t('enableWithQRCode.provisioningFailed')
        this.$store.dispatch('toast/error', { title })
      } finally {
        this.loading = false
      }
    },
    async checkCode(code) {
      this.checkCodeLoading = true
      try {
        const params = { code }
        const { data } = await TwoFactorAuthService(this.$client).configure(
          'totp',
          params
        )
        const title = this.$t('enableWithQRCode.checkSuccess')
        this.$store.dispatch('toast/success', { title })
        this.$emit('verified', data.backup_codes)
      } catch (error) {
        this.checkCodeLoading = false
        this.$refs.authCodeInput.reset()
        const title = this.$t('enableWithQRCode.verificationFailed')
        this.$store.dispatch('toast/error', { title })
      }
    },
  },
}
</script>
