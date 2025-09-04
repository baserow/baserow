<template>
  <div>
    <h2 class="box__title">{{ $t('twoFactorAuthSettings.title') }}</h2>
    <TwoFactorAuthEmpty />
  </div>
</template>

<script>
import TwoFactorAuthEmpty from '@baserow/modules/core/components/settings/twoFactorAuth/TwoFactorAuthEmpty'

export default {
  name: 'TwoFactorAuthSettings',
  components: { TwoFactorAuthEmpty },
}
</script>
