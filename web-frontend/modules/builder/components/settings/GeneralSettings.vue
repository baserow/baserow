<template>
  <div>
    <Error :error="error"></Error>
    <BuilderGeneralSettingsForm
      ref="settingsForm"
      :default-values="builder"
      @values-changed="updateApplication($event)"
    />
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import BuilderGeneralSettingsForm from '@baserow/modules/builder/components/form/BuilderGeneralSettingsForm'
import _ from 'lodash'

export default {
  name: 'GeneralSettings',
  components: { BuilderGeneralSettingsForm },
  mixins: [error],
  provide() {
    return {
      builder: this.builder,
      page: null,
      mode: null,
    }
  },
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  methods: {
    async updateApplication(values) {
      // In this case there weren't any actual changes
      if (_.isMatch(this.builder, values)) {
        return
      }

      try {
        await this.$store.dispatch('application/update', {
          application: this.builder,
          values,
        })
      } catch (error) {
        let title = this.$t('generalSettings.cantUpdateApplicationTitle')
        let message = this.$t(
          'generalSettings.cantUpdateApplicationDescription'
        )
        if (values?.favicon_file?.name) {
          title = this.$t('generalSettings.cantUploadFaviconTitle')
          message = this.$t('generalSettings.cantUploadFaviconDescription')
        }
        this.$store.dispatch('toast/error', { title, message })
        this.$refs.settingsForm.reset()
      }
    },
    getTitle() {
      return this.$t('generalSettings.titleOverview')
    },
  },
}
</script>
