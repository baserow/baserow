<template>
  <div>
    <h3>{{ $t('disableTwoFactorAuth.title') }}</h3>
    <div class="disable-two-factor__description">
      {{ $t('disableTwoFactorAuth.description') }}
    </div>

    <Error :error="error"></Error>

    <form @submit.prevent="confirm">
      <FormGroup
        :error="v$.values.password.$error"
        :label="'Password'"
        required
        small-label
        class="margin-bottom-2"
      >
        <FormInput
          v-model="v$.values.password.$model"
          :error="v$.values.password.$error"
          type="password"
          size="large"
          @blur="v$.values.password.$touch"
        >
        </FormInput>

        <template #error>
          {{ v$.values.password.$errors[0]?.$message }}
        </template>
      </FormGroup>

      <div class="actions actions--right actions--gap">
        <Button tag="a" type="secondary" size="large" @click="$emit('cancel')">
          {{ $t('disableTwoFactorAuth.cancel') }}
        </Button>
        <Button
          type="danger"
          size="large"
          :loading="loading"
          :disabled="loading || !values.password"
          @click="confirm"
        >
          {{ $t('disableTwoFactorAuth.disable') }}
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
        password: '',
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
        await TwoFactorAuthService(this.$client).disable(this.values.password)
        this.loading = false
        this.$emit('disabled')
        this.$store.dispatch('toast/success', {
          title: this.$t('disableTwoFactorAuth.successTitle'),
        })
      } catch (error) {
        this.loading = false
        this.handleError(error, 'twoFactor', {
          ERROR_WRONG_PASSWORD: new ResponseErrorMessage(
            this.$t('disableTwoFactorAuth.errorWrongPasswordTitle'),
            this.$t('disableTwoFactorAuth.errorWrongPasswordMessage')
          ),
        })
      }
    },
  },
  validations() {
    return {
      values: {
        password: {
          required,
        },
      },
    }
  },
}
</script>
