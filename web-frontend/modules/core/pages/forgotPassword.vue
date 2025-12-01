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
            :error="fieldHasErrors('email')"
            class="mb-32"
          >
            <FormInput
              ref="email"
              v-model="values.email"
              :error="fieldHasErrors('email')"
              :disabled="success"
              size="large"
              @blur="v$.values.email.$touch"
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
        {{ $t('forgotPassword.confirmation', { email: values.email }) }}
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
import { required, email } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import { reactive } from 'vue'

import error from '@baserow/modules/core/mixins/error'
import form from '@baserow/modules/core/mixins/form'
import AuthService from '@baserow/modules/core/services/auth'
import LangPicker from '@baserow/modules/core/components/LangPicker'
import { mapGetters } from 'vuex'

export default {
  components: { LangPicker },
  mixins: [error, form],
  layout: 'login',
  setup() {
    const values = reactive({
      values: {
        email: '',
      },
    })

    const rules = {
      values: {
        email: { required, email },
      },
    }
    return {
      v$: useVuelidate(rules, values, { $lazy: true }),
      values: values.values,
    }
  },
  data() {
    return {
      loading: false,
      success: false,
    }
  },
  head() {
    return {
      title: this.$t('forgotPassword.title'),
      link: [
        {
          rel: 'canonical',
          href:
            this.$config.PUBLIC_WEB_FRONTEND_URL +
            this.$router.resolve({ name: 'forgot-password' }).href,
        },
      ],
    }
  },
  computed: {
    ...mapGetters({
      settings: 'settings/get',
    }),
  },
  methods: {
    async sendLink() {
      const isFormCorrect = await this.v$.$validate()
      if (!isFormCorrect) return

      this.loading = true
      this.hideError()

      try {
        const resetUrl = `${this.$config.BASEROW_EMBEDDED_SHARE_URL}/reset-password`
        await AuthService(this.$client).sendResetPasswordEmail(
          this.values.email,
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
}
</script>
