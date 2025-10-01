<template>
  <div>
    <h3>Are you sure you want to disable 2FA?</h3>
    <div class="disable-two-factor__description">Your account will lose an extra layer of security. If someone finds out your password, they might be able to log in to your account.</div>

    <Error :error="error"></Error>

    <form @submit.prevent="confirm">
      <FormGroup
        :error="v$.values.passwordConfirm.$error"
        :label="'Password'"
        required
        small-label
        class="margin-bottom-2"
      >
        <FormInput
          v-model="v$.values.passwordConfirm.$model"
          :error="v$.values.passwordConfirm.$error"
          type="password"
          size="large"
          @blur="v$.values.passwordConfirm.$touch"
        >
        </FormInput>

        <template #error>
          {{ v$.values.passwordConfirm.$errors[0]?.$message }}
        </template>
      </FormGroup>

      <div class="actions actions--right actions--gap">
        <Button
          type="secondary"
          size="large"
          @click="$emit('cancel')"
        >
          Leave it on
        </Button>
        <Button
          type="danger"
          size="large"
          :loading="loading"
          :disabled="loading || !values.passwordConfirm"
          @click="confirm"
        >
          Disable
        </Button>
      </div>
    </form>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'

import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import TwoFactorAuthService from '@baserow/modules/core/services/twoFactorAuth'

export default {
  name: 'DisableTwoFactorAuth',
  mixins: [error],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        passwordConfirm: '',
      },
      loading: false,
    }
  },
  methods: {
    async confirm() {
      this.v$.$touch()

      if (this.v$.$invalid) {
        return
      }

      this.loading = true
      this.hideError()

      try {
        await TwoFactorAuthService(this.$client).disable(
          this.account.confirmPassword
        )
        this.loading = false

        this.$emit('disabled')
        // TODO: toast
      } catch (error) {
        this.loading = false
        // TODO:
        // this.handleError(error, 'changePassword', {
        //   ERROR_INVALID_OLD_PASSWORD: new ResponseErrorMessage(
        //     this.$t('passwordSettings.errorInvalidOldPasswordTitle'),
        //     this.$t('passwordSettings.errorInvalidOldPasswordMessage')
        //   ),
        // })
      }
    },
  },
  validations() {
    return {
      values: {
        passwordConfirm: {
          required,
        },
      },
    }
  },
}
</script>
