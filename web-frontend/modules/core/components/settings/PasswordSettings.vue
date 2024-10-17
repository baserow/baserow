<template>
  <div>
    <Error :error="error"></Error>
    <Alert v-if="success" type="success">
      <template #title>{{ $t('passwordSettings.changedTitle') }}</template>
      <p>{{ $t('passwordSettings.changedDescription') }}</p>
    </Alert>

    <PasswordForm ref="form" @submitted="submitted"> </PasswordForm>
  </div>
</template>

<script>
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import AuthService from '@baserow/modules/core/services/auth'
import PasswordForm from '@baserow/modules/core/components/settings/PasswordForm'

export default {
  components: { PasswordForm },
  mixins: [error],
  data() {
    return {
      success: false,
    }
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
        await AuthService(this.$client).changePassword(
          values.oldPassword,
          values.newPassword
        )
        // Changing the password invalidates all the refresh and access token, so we
        // have to log in again. This can be done with the new password we still have
        // in memory.
        await this.$store.dispatch('auth/login', {
          email: this.$store.getters['auth/getUsername'],
          password: values.newPassword,
        })
        this.success = true
        this.$emit('loading', false)
      } catch (error) {
        this.$emit('loading', false)
        this.handleError(error, 'changePassword', {
          ERROR_INVALID_OLD_PASSWORD: new ResponseErrorMessage(
            this.$t('passwordSettings.errorInvalidOldPasswordTitle'),
            this.$t('passwordSettings.errorInvalidOldPasswordMessage')
          ),
        })
      }
    },
    getCTALabel() {
      return this.$t('passwordSettings.submitButton')
    },
  },
}
</script>
