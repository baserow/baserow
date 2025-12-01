<template>
  <div>
    <EnableWithQRCode v-if="state == 'qr_code'" @verified="stepVerified" />
    <SaveBackupCode
      v-if="state == 'save_code'"
      :backup-codes="backupCodes"
      @continue="stepEnabled"
    />
  </div>
</template>

<script>
import EnableWithQRCode from '@baserow/modules/core/components/settings/twoFactorAuth/EnableWithQRCode'
import SaveBackupCode from '@baserow/modules/core/components/settings/twoFactorAuth/SaveBackupCode'

export default {
  name: 'EnableTOTP',
  components: { EnableWithQRCode, SaveBackupCode },
  props: {},
  data() {
    return {
      state: 'qr_code',
      backupCodes: [],
    }
  },
  methods: {
    stepVerified(backupCodes) {
      this.state = 'save_code'
      this.backupCodes = backupCodes
    },
    stepEnabled() {
      this.$emit('enabled')
    },
  },
}
</script>
