<template>
  <div class="saml-auth-link">
    <ABButton @click.prevent="onClick()">
      {{ buttonLabel }}
    </ABButton>
    <Modal ref="modal">
      <ThemeProvider>
        <form @submit.prevent="">
          <ABFormGroup
            v-if="hasMultipleSamlProvider"
            :label="$t('samlAuthLink.provideEmail')"
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
              :placeholder="$t('samlAuthLink.emailPlaceholder')"
              @blur="$v.values.email.$touch()"
            />
          </ABFormGroup>
          <div class="saml-auth-link__modal-footer">
            <ABButton class="margin-top-2" @click.prevent.stop="login()">
              {{ buttonLabel }}
            </ABButton>
          </div>
        </form>
      </ThemeProvider>
    </Modal>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import { required, email } from 'vuelidate/lib/validators'
import ThemeProvider from '@baserow/modules/builder/components/theme/ThemeProvider'

export default {
  components: { ThemeProvider },
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
      values: { email: '' },
    }
  },
  computed: {
    isAuthenticated() {
      return this.$store.getters['userSourceUser/isAuthenticated'](this.builder)
    },
    hasMultipleSamlProvider() {
      return this.authProviders.length > 1
    },
    isEditMode() {
      return this.mode === 'editing'
    },
    buttonLabel() {
      return this.$t('samlAuthLink.placeholderWithSaml', {
        login: this.loginButtonLabel,
      })
    },
  },
  methods: {
    async onClick() {
      if (this.hasMultipleSamlProvider) {
        this.$refs.modal.show()
      } else {
        await this.login()
      }
    },
    async login() {
      if (this.isAuthenticated) {
        await this.$store.dispatch('userSourceUser/logoff', {
          application: this.builder,
        })
      }

      if (this.hasMultipleSamlProvider) {
        this.$v.$touch()

        if (this.$v.$invalid) {
          this.focusOnFirstError()
          return
        }
      }

      this.loading = true
      this.hideError()

      const dest = `${
        this.$config.PUBLIC_BACKEND_URL
      }/api/user-source/${encodeURIComponent(
        this.userSource.uid
      )}/sso/saml/login/`

      const urlWithParams = new URL(dest)

      if (this.hasMultipleSamlProvider) {
        urlWithParams.searchParams.append('email', this.values.email)
      }

      // Add the current url as get parameter to be redirected here after the login.
      urlWithParams.searchParams.append('original', window.location)

      window.location = urlWithParams.toString()
    },
  },
  validations: {
    values: {
      email: { required, email },
    },
  },
}
</script>
