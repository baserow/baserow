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
            :error-message="v$.values.email.$errors[0]?.$message"
            :autocomplete="isEditMode ? 'off' : ''"
            required
          >
            <ABInput
              v-model="v$.values.email.$model"
              :placeholder="$t('samlAuthLink.emailPlaceholder')"
              @blur="v$.values.email.$touch"
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
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import { required, email, helpers } from '@vuelidate/validators'
import ThemeProvider from '@baserow/modules/builder/components/theme/ThemeProvider'

export default {
  components: { ThemeProvider },
  mixins: [form, error],
  props: {
    userSource: { type: Object, required: true },
    authProviders: {
      type: Array,
      required: true,
    },
    authProviderType: {
      type: Object,
      required: true,
    },
    loginButtonLabel: {
      type: String,
      required: true,
    },
    readonly: {
      type: Boolean,
      required: false,
      default: false,
    },
    authenticate: {
      type: Function,
      required: true,
    },
    beforeLogin: {
      type: Function,
      required: false,
      default: () => {
        return () => {}
      },
    },
    afterLogin: {
      type: Function,
      required: false,
      default: () => {
        return () => {}
      },
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      loading: false,
      values: { email: '' },
    }
  },
  computed: {
    hasMultipleSamlProvider() {
      return this.authProviders.length > 1
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
      await this.beforeLogin()

      if (this.hasMultipleSamlProvider) {
        this.v$.$touch()

        if (this.v$.$invalid) {
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
  validations() {
    return {
      values: {
        email: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          email: helpers.withMessage(this.$t('error.invalidEmail'), email),
        },
      },
    }
  },
}
</script>
