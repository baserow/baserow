<template>
  <div>
    <Error :error="error"></Error>
    <Alert v-if="success" type="success">
      <template #title>{{ $t('accountSettings.changedTitle') }}</template>
      <p>{{ $t('accountSettings.changedDescription') }}</p>
    </Alert>
    <AccountForm ref="form" :default-values="user" @submitted="submitted">
    </AccountForm>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import error from '@baserow/modules/core/mixins/error'
import AccountForm from '@baserow/modules/core/components/settings/AccountForm'

export default {
  components: { AccountForm },
  mixins: [error],
  data() {
    return {
      success: false,
    }
  },
  computed: {
    ...mapGetters({
      user: 'auth/getUserObject',
    }),
  },
  methods: {
    submitForm() {
      this.$refs.form.submit()
    },
    async submitted(values) {
      this.success = false
      this.$emit('loading', true)
      this.hideError()

      try {
        const data = await this.$store.dispatch('auth/update', values)
        this.$i18n.setLocale(data.language)
        this.success = true
        this.$emit('loading', false)
      } catch (error) {
        this.$emit('loading', false)
        this.handleError(error)
      }
    },
    getCTALabel() {
      return this.$t('accountSettings.submitButton')
    },
  },
}
</script>
