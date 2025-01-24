<template>
  <div
    class="auth__wrapper"
    :class="{ 'auth__wrapper--small-centered': success }"
  >
    <div v-if="!success">
      <div class="auth__logo">
        <nuxt-link :to="{ name: 'index' }">
          <Logo />
        </nuxt-link>
      </div>
      <div class="auth__head auth__head-title">
        <h1 class="margin-bottom-0">{{ $t('forgotPassword.title') }}</h1>
        <LangPicker />
      </div>

      <!-- Disabled info message -->
      <template v-if="!settings.allow_reset_password">
        <Alert type="error">
          <template #title>{{ $t('forgotPassword.disabled') }}</template>
          <p>{{ $t('forgotPassword.disabledMessage') }}</p>
        </Alert>
        <nuxt-link :to="{ name: 'login' }">
          <Button>{{ $t('action.backToLogin') }}</Button>
        </nuxt-link>
      </template>

      <!-- Form -->
      <div v-else>
        <p class="auth__head-text">
          {{ $t('forgotPassword.message') }}
        </p>
        <Error :error="error"></Error>
        <form @submit.prevent="sendLink">
          <FormGroup
            small-label
            :label="$t('field.emailAddress')"
            required
            :error="$v.account.email.$error"
            class="mb-32"
          >
            <FormInput
              ref="email"
              v-model="account.email"
              :error="$v.account.email.$error"
              :disabled="success"
              size="large"
              @blur="$v.account.email.$touch()"
            >
            </FormInput>
            <template #error>
              <i class="iconoir-warning-triangle"></i>
              {{ $t('error.invalidEmail') }}
            </template>
          </FormGroup>
          <div class="auth__action mb-32">
            <Button
              type="primary"
              full-width
              size="large"
              :loading="loading"
              :disabled="loading || success"
            >
              {{ $t('forgotPassword.submit') }}
            </Button>
          </div>
          <div>
            <ul class="auth__action-links">
              <li class="auth__action-link">
                <nuxt-link :to="{ name: 'login' }">
                  {{ $t('forgotPassword.goBack') }}
                </nuxt-link>
              </li>
            </ul>
          </div>
        </form>
      </div>
    </div>
    <div v-if="success" class="auth__wrapper auth__wrapper--small-centered">
      <ButtonIcon icon="iconoir-mail" type="secondary"></ButtonIcon>
      <h2>
        {{ $t('forgotPassword.confirmationTitle') }}
      </h2>
      <p>
        {{ $t('forgotPassword.confirmation', { email: account.email }) }}
      </p>
      <Button
        tag="nuxt-link"
        :to="{ name: 'login' }"
        type="primary"
        size="large"
      >
        {{ $t('action.backToLogin') }}</Button
      >
    </div>
  </div>
</template>

<script>
import { required, email } from 'vuelidate/lib/validators'

import error from '@baserow/modules/core/mixins/error'
import AuthService from '@baserow/modules/core/services/auth'
import LangPicker from '@baserow/modules/core/components/LangPicker'
import { mapGetters } from 'vuex'

export default {
  components: { LangPicker },
  mixins: [error],
  layout: 'login',
  data() {
    return {
      loading: false,
      success: false,
      account: {
        email: '',
      },
    }
  },
  head() {
    return {
      title: this.$t('forgotPassword.title'),
    }
  },
  computed: {
    ...mapGetters({
      settings: 'settings/get',
    }),
  },
  methods: {
    async sendLink() {
      this.$v.$touch()
      if (this.$v.$invalid) {
        return
      }

      this.loading = true
      this.hideError()

      try {
        const resetUrl = `${this.$config.BASEROW_EMBEDDED_SHARE_URL}/reset-password`
        await AuthService(this.$client).sendResetPasswordEmail(
          this.account.email,
          resetUrl
        )
        this.success = true
        this.loading = false
      } catch (error) {
        this.loading = false
        this.handleError(error, 'passwordReset')
      }
    },
  },
  validations: {
    account: {
      email: { required, email },
    },
  },
}
</script>
