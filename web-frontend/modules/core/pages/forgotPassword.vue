<template>
  <div>
    <div v-if="!success">
      <div class="auth__logo">
        <nuxt-link :to="{ name: 'index' }">
          <Logo />
        </nuxt-link>
      </div>
      <div class="auth__head auth__head--more-margin">
        <h1 class="auth__head-title">{{ $t('forgotPassword.title') }}</h1>
        <LangPicker />
      </div>

      <!-- Disabled info message -->
      <template v-if="!settings.allow_reset_password">
        <Alert type="error">
          <template #title>{{ $t('forgotPassword.disabled') }}</template>
          <p>{{ $t('forgotPassword.disabledMessage') }}</p>
        </Alert>
        <nuxt-link :to="{ name: 'login' }" class="button button--full-width">
          <i class="iconoir-arrow-left"></i>
          {{ $t('action.backToLogin') }}
        </nuxt-link>
      </template>

      <!-- Form -->
      <div v-else>
        <p>
          {{ $t('forgotPassword.message') }}
        </p>
        <Error :error="error"></Error>
        <form @submit.prevent="sendLink">
          <FormGroup
            small-label
            :label="$t('field.emailAddress')"
            required
            :error="v$.email.$error"
            class="margin-bottom-2"
          >
            <FormInput
              ref="email"
              v-model="state.email"
              :error="v$.email.$error"
              :disabled="success"
              size="large"
              @blur="v$.email.$touch()"
            >
            </FormInput>
            <template #error>
              <i class="iconoir-warning-triangle"></i>
              {{ $t('error.invalidEmail') }}
            </template>
          </FormGroup>
          <div class="auth__action">
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
              <li>
                {{ $t('forgotPassword.loginText') }}
                <nuxt-link :to="{ name: 'login' }">
                  {{ $t('action.login') }}
                </nuxt-link>
              </li>
            </ul>
          </div>
        </form>
      </div>
    </div>
    <div v-if="success" class="box__message">
      <div class="box__message-icon">
        <i class="iconoir-send"></i>
      </div>
      <p class="box__message-text">
        {{ $t('forgotPassword.confirmation') }}
      </p>

      <Button
        tag="nuxt-link"
        :to="{ name: 'login' }"
        type="primary"
        size="large"
        icon="iconoir-arrow-left"
      >
        {{ $t('action.backToLogin') }}</Button
      >
    </div>
  </div>
</template>

<script>
import { required, email } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'

import error from '@baserow/modules/core/mixins/error'
import AuthService from '@baserow/modules/core/services/auth'
import LangPicker from '@baserow/modules/core/components/LangPicker'
import { mapGetters } from 'vuex'

export default {
  components: { LangPicker },
  mixins: [error],
  layout: 'login',
  setup() {
    const state = reactive({
      email: '',
    })

    const rules = computed(() => ({
      email: { required, email },
    }))

    const v$ = useVuelidate(rules, state)
    return { v$, state }
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
    }
  },
  computed: {
    ...mapGetters({
      settings: 'settings/get',
    }),
  },
  methods: {
    async sendLink() {
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }

      this.loading = true
      this.hideError()

      try {
        const resetUrl = `${this.$config.BASEROW_EMBEDDED_SHARE_URL}/reset-password`
        await AuthService(this.$client).sendResetPasswordEmail(
          this.state.email,
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
