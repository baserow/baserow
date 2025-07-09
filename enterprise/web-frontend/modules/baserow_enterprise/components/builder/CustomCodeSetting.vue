<template>
  <CustomCodeSettingForm
    ref="settingsForm"
    :default-values="builder"
    @values-changed="onValuesChanged"
  />
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import { isSubObject } from '@baserow/modules/core/utils/object'
import CustomCodeSettingForm from '@baserow_enterprise/components/builder/CustomCodeSettingForm.vue'

export default {
  name: 'CustomCodeSetting',
  components: { CustomCodeSettingForm },
  mixins: [error],
  provide() {
    return {
      builder: this.builder,
      mode: null,
    }
  },
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      debounceTimeout: null,
    }
  },
  methods: {
    async updateApplication(values) {
      if (!this.$refs.settingsForm.isFormValid(true)) {
        return
      }

      // In this case there weren't any actual changes
      if (isSubObject(this.builder, values)) {
        return
      }

      try {
        await this.$store.dispatch('application/update', {
          application: this.builder,
          values,
        })
      } catch (error) {
        const title = this.$t('generalSettings.cantUpdateApplicationTitle')
        const message = this.$t(
          'generalSettings.cantUpdateApplicationDescription'
        )
        this.$store.dispatch('toast/error', { title, message })
        this.$refs.settingsForm.reset()
      }
    },
    debouncedUpdate(val) {
      clearTimeout(this.debounceTimeout)
      this.debounceTimeout = setTimeout(() => {
        this.updateApplication(val)
      }, 500)
    },
    onValuesChanged(newValues) {
      this.debouncedUpdate(newValues)
    },
  },
}
</script>
