<template>
  <div>
    <Alert v-if="invitation !== null" type="info-primary">
      <template #title>{{ $t('invitationTitle') }}</template>
      <i18n path="invitationMessage" tag="p">
        <template #invitedBy>
          <strong>{{ invitation.invited_by }}</strong>
        </template>
        <template #workspace>
          <strong>{{ invitation.workspace }}</strong>
        </template>
      </i18n>
    </Alert>
    <Error :error="error"></Error>
    <form @submit.prevent="login">
      <FormGroup
        class="margin-bottom-2"
        required
        small-label
        :label="$t('field.emailAddress')"
        :error="fieldHasErrors('email')"
      >
        <FormInput
          v-if="invitation !== null"
          ref="email"
          type="email"
          size="large"
          disabled
          :value="state.email"
        ></FormInput>
        <FormInput
          v-else
          ref="email"
          v-model="state.email"
          type="email"
          size="large"
          :error="fieldHasErrors('email')"
          :placeholder="$t('login.emailPlaceholder')"
          autocomplete="username"
          @blur="v$.email.$touch"
        />

        <template #error>
          <i class="iconoir-warning-triangle"></i>
          {{ $t('error.invalidEmail') }}</template
        >
      </FormGroup>

      <FormGroup
        required
        small-label
        :label="$t('field.password')"
        :error="fieldHasErrors('password')"
      >
        <FormInput
          ref="password"
          v-model="state.password"
          type="password"
          size="large"
          :error="fieldHasErrors('password')"
          :placeholder="$t('login.passwordPlaceholder')"
          autocomplete="current-password"
          @blur="v$.password.$touch"
        />
        <template #error>
          <i class="iconoir-warning-triangle"></i>
          {{ $t('error.passwordRequired') }}
        </template>
      </FormGroup>

      <div class="auth__action">
        <Button
          type="primary"
          size="large"
          :loading="loading"
          full-width
          :disabled="loading"
        >
          {{ $t('action.signIn') }}
        </Button>
      </div>
    </form>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required, email } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import WorkspaceService from '@baserow/modules/core/services/workspace'

export default {
  name: 'PasswordLogin',
  mixins: [form, error],
  props: {
    invitation: {
      required: false,
      validator: (prop) => typeof prop === 'object' || prop === null,
      default: null,
    },
  },
  setup() {
    const state = reactive({
      email: '',
      password: '',
    })

    const rules = computed(() => ({
      email: { required, email },
      password: { required },
    }))

    const v$ = useVuelidate(rules, state)
    return { v$, state }
  },
  data() {
    return {
      loading: false,
    }
  },
  beforeMount() {
    if (this.invitation !== null) {
      this.state.email = this.invitation.email
    }
  },
  async mounted() {
    if (!this.$config.BASEROW_DISABLE_PUBLIC_URL_CHECK) {
      const publicBackendUrl = new URL(this.$config.PUBLIC_BACKEND_URL)
      if (publicBackendUrl.host !== window.location.host) {
        // If the host of the browser location does not match the PUBLIC_BACKEND_URL
        // then we are probably mis-configured.
        try {
          // Attempt to connect to the backend using the configured PUBLIC_BACKEND_URL
          // just in-case it is actually configured correctly.
          await this.$client.get('_health/')
        } catch (error) {
          const publicBackendUrlWithProto =
            publicBackendUrl.protocol + '//' + publicBackendUrl.host
          const browserWindowUrl = location.protocol + '//' + location.host
          this.showError(
            'Backend URL mis-configuration detected',
            `Cannot connect to the backend at ${publicBackendUrlWithProto}.` +
              ` You visited Baserow at ${browserWindowUrl} ` +
              ' which indicates you have mis-configured the Baserow ' +
              ' BASEROW_PUBLIC_URL or PUBLIC_BACKEND_URL environment variables. ' +
              ' Please visit https://baserow.io/docs/tutorials/debugging-connection-issues ' +
              ' on how to fix this error.'
          )
        }
      }
    }
  },
  methods: {
    async login() {
      this.v$.$touch()
      const formValid = await this.v$.$validate()
      if (!formValid) {
        this.focusOnFirstError()
        return
      }

      this.loading = true
      this.hideError()

      try {
        const data = await this.$store.dispatch('auth/login', {
          email: this.state.email,
          password: this.state.password,
        })

        // If there is an invitation we can immediately accept that one after the user
        // successfully signs in.
        if (this.invitation?.email === this.state.email) {
          await WorkspaceService(this.$client).acceptInvitation(
            this.invitation.id
          )
        }

        this.$i18n.setLocale(data.language)
        this.$emit('success')
      } catch (error) {
        if (error.handler) {
          const response = error.handler.response
          if (response && response.status === 401) {
            if (response.data?.error === 'ERROR_DEACTIVATED_USER') {
              this.showError(
                this.$t('error.disabledAccountTitle'),
                this.$t('error.disabledAccountMessage')
              )
            } else if (
              response.data?.error === 'ERROR_AUTH_PROVIDER_DISABLED'
            ) {
              this.showError(
                this.$t('clientHandler.disabledPasswordProviderTitle'),
                this.$t('clientHandler.disabledPasswordProviderMessage')
              )
            } else if (
              response.data?.error === 'ERROR_EMAIL_VERIFICATION_REQUIRED'
            ) {
              this.$emit('email-not-verified', this.state.email)
            } else {
              this.showError(
                this.$t('error.incorrectCredentialTitle'),
                this.$t('error.incorrectCredentialMessage')
              )
            }

            this.state.password = ''
            this.v$.$reset()
            this.$refs.password.focus()
          } else {
            const message = error.handler.getMessage('login')
            this.showError(message)
          }

          this.loading = false
          error.handler.handled()
        } else {
          throw error
        }
      }
    },
  },
}
</script>
