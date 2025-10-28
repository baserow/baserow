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
          <ButtonText
            v-if="secret"
            class="enable-with-qr-code__copy"
            :type="'primary'"
            @click="copy"
          >
            {{ $t('enableWithQRCode.clickToCopy') }}
          </ButtonText>
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
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

export default {
  name: 'EnableWithQRCode',
  components: { AuthCodeInput },
  data() {
    return {
      loading: false,
      checkCodeLoading: false,
      qr_code: null,
      provisioning_url: null,
    }
  },
  computed: {
    secret() {
      if (this.provisioning_url) {
        const url = new URL(this.provisioning_url)
        return url.searchParams.get('secret')
      }
      return ''
    },
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
        this.provisioning_url = data.provisioning_url
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
    copy() {
      copyToClipboard(this.secret)
      this.$store.dispatch('toast/success', {
        title: this.$t('enableWithQRCode.secretCopiedTitle'),
        message: this.$t('enableWithQRCode.secretCopiedMessage'),
      })
    },
  },
}
</script>
