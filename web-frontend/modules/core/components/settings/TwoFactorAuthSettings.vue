<template>
  <div>
    <h2 class="box__title">{{ $t('twoFactorAuthSettings.title') }}</h2>
    <TwoFactorAuthEmpty v-if="state == 'empty'" @enable="enable" />
    <EnableTwoFactorOptions v-if="state == 'pick_options'" @cancel="cancel" @continue="stepContinue" />
    <EnableWithQRCode v-if="state == 'qr_code'" />
  </div>
</template>

<script>
import TwoFactorAuthEmpty from '@baserow/modules/core/components/settings/twoFactorAuth/TwoFactorAuthEmpty'
import EnableTwoFactorOptions from '@baserow/modules/core/components/settings/twoFactorAuth/EnableTwoFactorOptions'
import EnableWithQRCode from '@baserow/modules/core/components/settings/twoFactorAuth/EnableWithQRCode'

export default {
  name: 'TwoFactorAuthSettings',
  components: { TwoFactorAuthEmpty, EnableTwoFactorOptions, EnableWithQRCode },
  data() {
    return {
      state: 'empty',
    }
  },
  methods: {
    enable() {
      this.state = 'pick_options'
    },
    stepContinue() {
      this.state = 'qr_code'
    },
    cancel() {
      this.state = 'empty'
    },
  },
}
</script>
