<template>
  <form class="auth-form-element" @submit.prevent="onLogin">
    <Error :error="error"></Error>
    <ABFormGroup
      :label="$t('authFormElement.email')"
      :error-message="
        $v.values.email.$dirty
          ? !$v.values.email.required
            ? $t('error.requiredField')
            : !$v.values.email.email
            ? $t('error.invalidEmail')
            : ''
          : ''
      "
      :autocomplete="isEditMode ? 'off' : ''"
      required
    >
      <ABInput
        v-model="values.email"
        :placeholder="$t('authFormElement.emailPlaceholder')"
        @blur="$v.values.email.$touch()"
      />
    </ABFormGroup>
    <ABFormGroup
      :label="$t('authFormElement.password')"
      :error-message="
        $v.values.password.$dirty
          ? !$v.values.password.required
            ? $t('error.requiredField')
            : ''
          : ''
      "
      required
    >
      <ABInput
        ref="passwordRef"
        v-model="values.password"
        type="password"
        :placeholder="$t('authFormElement.passwordPlaceholder')"
        @blur="$v.values.password.$touch()"
      />
    </ABFormGroup>
    <div class="auth-form__footer">
      <ABButton :disabled="$v.$error" :loading="loading" size="large">
        {{ loginButtonLabel }}
      </ABButton>
    </div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import { required, email } from 'vuelidate/lib/validators'

export default {
  mixins: [form, error],
  inject: ['builder', 'mode'],
  props: {
    userSource: { type: Object, required: true },
    authProviders: {
      type: Array,
      required: true,
    },
    loginButtonLabel: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      values: { email: '', password: '' },
    }
  },
  computed: {
    isAuthenticated() {
      return this.$store.getters['userSourceUser/isAuthenticated'](this.builder)
    },
    isEditMode() {
      return this.mode === 'editing'
    },
  },
  methods: {
    async onLogin(event) {
      if (this.isAuthenticated) {
        await this.$store.dispatch('userSourceUser/logoff', {
          application: this.builder,
        })
      }

      this.$v.$touch()
      if (this.$v.$invalid) {
        this.focusOnFirstError()
        return
      }
      this.loading = true
      this.hideError()
      try {
        await this.$store.dispatch('userSourceUser/authenticate', {
          application: this.builder,
          userSource: this.userSource,
          credentials: {
            email: this.values.email,
            password: this.values.password,
          },
          setCookie: this.mode === 'public',
        })
        this.values.password = ''
        this.values.email = ''
        this.$v.$reset()
        this.$emit('after-login')
      } catch (error) {
        if (error.handler) {
          const response = error.handler.response
          if (response && response.status === 401) {
            this.values.password = ''
            this.$v.$reset()
            this.$v.$touch()
            this.$refs.passwordRef.focus()

            if (response.data?.error === 'ERROR_INVALID_CREDENTIALS') {
              this.showError(
                this.$t('error.incorrectCredentialTitle'),
                this.$t('error.incorrectCredentialMessage')
              )
            }
          } else {
            const message = error.handler.getMessage('login')
            this.showError(message)
          }

          error.handler.handled()
        } else {
          throw error
        }
      }
      this.loading = false
    },
  },
  validations: {
    values: {
      email: { required, email },
      password: { required },
    },
  },
}
</script>
