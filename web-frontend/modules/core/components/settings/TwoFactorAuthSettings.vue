<template>
  <div>
    <h2 class="box__title">{{ $t('twoFactorAuthSettings.title') }}</h2>
    <div v-if="!loading">
      <TwoFactorAuthEmpty v-if="state == 'empty'" @enable="enable" />
      <EnableTwoFactorOptions
        v-if="state == 'pick_options'"
        @cancel="cancel"
        @continue="stepContinue"
      />
      <EnableWithQRCode v-if="state == 'qr_code'" @verified="stepVerified" />
      <SaveBackupCode v-if="state == 'save_code'" :backup-codes="backupCodes" />
    </div>
  </div>
</template>

<script>
import TwoFactorAuthEmpty from '@baserow/modules/core/components/settings/twoFactorAuth/TwoFactorAuthEmpty'
import EnableTwoFactorOptions from '@baserow/modules/core/components/settings/twoFactorAuth/EnableTwoFactorOptions'
import EnableWithQRCode from '@baserow/modules/core/components/settings/twoFactorAuth/EnableWithQRCode'
import SaveBackupCode from '@baserow/modules/core/components/settings/twoFactorAuth/SaveBackupCode'
import TwoFactorAuthService from '@baserow/modules/core/services/twoFactorAuth'

export default {
  name: 'TwoFactorAuthSettings',
  components: {
    TwoFactorAuthEmpty,
    EnableTwoFactorOptions,
    EnableWithQRCode,
    SaveBackupCode,
  },
  data() {
    return {
      loading: true,
      state: 'empty',
      backupCodes: [],
    }
  },
  async mounted() {
    // TODO: loading, error
    this.loading = true
    try {
      const { data } = await TwoFactorAuthService(
        this.$client
      ).getConfiguration()
      console.log({ data })

      if (data.type === 'totp') {
        if (data.enabled) {
          this.state = 'save_code'
        } else {
          this.state = 'pick_options'
        }
      }
    } catch (error) {
      this.handleError(error)
    } finally {
      this.loading = false
    }
  },
  methods: {
    enable() {
      this.state = 'pick_options'
    },
    stepContinue() {
      this.state = 'qr_code'
    },
    stepVerified(backupCodes) {
      this.state = 'save_code'
      this.backupCodes = backupCodes
    },
    cancel() {
      this.state = 'empty'
    },
  },
}
</script>
