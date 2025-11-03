<template>
  <div>
    <h2 class="box__title">{{ $t('twoFactorAuthSettings.title') }}</h2>
    <div v-if="!loading">
      <TwoFactorAuthEmpty
        v-if="state == 'empty'"
        :allowed="allowed"
        @enable="state = 'pick_options'"
      />
      <EnableTwoFactorOptions
        v-if="state == 'pick_options'"
        @cancel="state = 'empty'"
        @continue="stepContinue"
      />
      <component
        :is="twoFactorSettingsComponent"
        v-if="twoFactorSettingsComponent && state == 'configure'"
        @enabled="stepEnabled"
      />
      <TwoFactorEnabled
        v-if="state == 'enabled'"
        :provider="provider"
        @disable="state = 'disable'"
      />
      <DisableTwoFactorAuth
        v-if="state == 'disable'"
        @cancel="state = 'enabled'"
        @disabled="state = 'empty'"
      />
    </div>
    <div v-if="loading" class="loading-spinner"></div>
  </div>
</template>

<script>
import TwoFactorAuthEmpty from '@baserow/modules/core/components/settings/twoFactorAuth/TwoFactorAuthEmpty'
import DisableTwoFactorAuth from '@baserow/modules/core/components/settings/twoFactorAuth/DisableTwoFactorAuth'
import TwoFactorEnabled from '@baserow/modules/core/components/settings/twoFactorAuth/TwoFactorEnabled'
import EnableTwoFactorOptions from '@baserow/modules/core/components/settings/twoFactorAuth/EnableTwoFactorOptions'
import TwoFactorAuthService from '@baserow/modules/core/services/twoFactorAuth'

export default {
  name: 'TwoFactorAuthSettings',
  components: {
    TwoFactorAuthEmpty,
    EnableTwoFactorOptions,
    TwoFactorEnabled,
    DisableTwoFactorAuth,
  },
  data() {
    return {
      loading: true,
      state: 'empty',
      provider: null,
      allowed: false,
      twoFactorSettingsComponent: null,
    }
  },
  async mounted() {
    await this.loadConfiguration()
  },
  methods: {
    async loadConfiguration() {
      this.loading = true
      try {
        const { data } = await TwoFactorAuthService(
          this.$client
        ).getConfiguration()
        if (data.is_enabled) {
          this.state = 'enabled'
          this.provider = data
        }
        this.allowed = data.allowed
      } catch (error) {
        const title = this.$t('twoFactorAuthSettings.loadingError')
        this.$store.dispatch('toast/error', { title })
      } finally {
        this.loading = false
      }
    },
    stepContinue(choice) {
      const type = this.$registry.get('twoFactorAuth', choice)
      this.state = 'configure'
      this.twoFactorSettingsComponent = type.settingsComponent
    },
    async stepEnabled() {
      await this.loadConfiguration()
    },
  },
}
</script>
