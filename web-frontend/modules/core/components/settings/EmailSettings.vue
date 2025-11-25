<template>
  <div>
    <h2 class="box__title">{{ $t('emailSettings.title') }}</h2>
    <Error :error="error"></Error>
    <Alert v-if="success" type="success">
      <template #title>{{ $t('emailSettings.successTitle') }}</template>
      <p>{{ $t('emailSettings.successDescription') }}</p>
    </Alert>
    <form v-if="!success" @submit.prevent="sendChangeEmailConfirmation">
      <FormGroup
        :label="$t('emailSettings.currentEmailLabel')"
        small-label
        required
        class="margin-bottom-2"
      >
        <FormInput
          :value="$store.getters['auth/getUsername']"
          type="email"
          size="large"
          disabled
        ></FormInput>
      </FormGroup>

      <FormGroup
        :label="$t('emailSettings.newEmailLabel')"
        small-label
        required
        :error="v$.emailData.newEmail.$dirty && v$.emailData.newEmail.$invalid"
        class="margin-bottom-2"
      >
        <FormInput
          v-model="emailData.newEmail"
          :error="
            v$.emailData.newEmail.$dirty && v$.emailData.newEmail.$invalid
          "
          type="email"
          size="large"
          @blur="v$.emailData.newEmail.$touch()"
        ></FormInput>
        <template #error>
          <span v-if="v$.emailData.newEmail.$dirty">
            {{ v$.emailData.newEmail.$errors[0]?.$message }}
          </span>
        </template>
      </FormGroup>

      <FormGroup
        :label="$t('emailSettings.passwordLabel')"
        small-label
        required
        :error="v$.emailData.password.$dirty && v$.emailData.password.$invalid"
        class="margin-bottom-2"
      >
        <FormInput
          v-model="emailData.password"
          :error="
            v$.emailData.password.$dirty && v$.emailData.password.$invalid
          "
          type="password"
          size="large"
          @blur="v$.emailData.password.$touch()"
        ></FormInput>
        <template #error>
          <span v-if="v$.emailData.password.$dirty">
            {{ v$.emailData.password.$errors[0]?.$message }}
          </span>
        </template>
      </FormGroup>

      <div class="actions actions--right">
        <Button
          type="primary"
          size="large"
          :loading="loading"
          :disabled="loading"
          icon="iconoir-mail"
        >
          {{ $t('emailSettings.submitButton') }}
        </Button>
      </div>
    </form>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, email, helpers } from '@vuelidate/validators'

import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import AuthService from '@baserow/modules/core/services/auth'

export default {
  mixins: [error],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      emailData: {
        newEmail: '',
        password: '',
      },
      loading: false,
      success: false,
    }
  },
  methods: {
    async sendChangeEmailConfirmation() {
      this.v$.$touch()

      if (this.v$.$invalid) {
        return
      }

      this.loading = true
      this.hideError()

      try {
        const baseUrl = `${this.$config.PUBLIC_WEB_FRONTEND_URL}/change-email`
        await AuthService(this.$client).sendChangeEmailConfirmation(
          this.emailData.newEmail,
          this.emailData.password,
          baseUrl
        )
        this.success = true
        this.loading = false
      } catch (error) {
        this.loading = false
        this.handleError(error, 'changeEmail', {
          ERROR_INVALID_OLD_PASSWORD: new ResponseErrorMessage(
            this.$t('emailSettings.errorInvalidPasswordTitle'),
            this.$t('emailSettings.errorInvalidPasswordMessage')
          ),
          ERROR_EMAIL_ALREADY_EXISTS: new ResponseErrorMessage(
            this.$t('emailSettings.errorEmailExistsTitle'),
            this.$t('emailSettings.errorEmailExistsMessage')
          ),
          ERROR_CHANGE_EMAIL_NOT_ALLOWED: new ResponseErrorMessage(
            this.$t('emailSettings.errorNotAllowedTitle'),
            this.$t('emailSettings.errorNotAllowedMessage')
          ),
        })
      }
    },
  },
  validations() {
    return {
      emailData: {
        newEmail: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          email: helpers.withMessage(this.$t('error.invalidEmail'), email),
        },
        password: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
