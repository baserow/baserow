<template>
  <div class="auth__wrapper">
    <div v-if="!success">
      <div class="auth__logo">
        <nuxt-link :to="{ name: 'index' }">
          <Logo />
        </nuxt-link>
      </div>

      <div class="auth__head auth__head-title">
        <h1>{{ $t('resetPassword.title') }}</h1>
        <LangPicker />
      </div>

      <!-- Disabled info message -->
      <template v-if="!settings.allow_reset_password">
        <Alert type="error">
          <template #title>{{ $t('resetPassword.disabled') }}</template>
          <p>{{ $t('resetPassword.disabledMessage') }}</p>
        </Alert>
        <nuxt-link :to="{ name: 'login' }" class="button button--full-width">
          <i class="iconoir-arrow-left"></i>
          {{ $t('action.backToLogin') }}
        </nuxt-link>
      </template>

      <!-- Form -->
      <div v-else>
        <Error :error="error"></Error>
        <form @submit.prevent="resetPassword">
          <FormGroup
            small-label
            :label="$t('resetPassword.newPassword')"
            required
            class="mb-24"
          >
            <PasswordInput
              v-model="account.password"
              :validation-state="v$.account.password"
              :placeholder="$t('signup.passwordPlaceholder')"
              :error-placeholder-class="'auth__control-error'"
              :show-error-icon="true"
            />
          </FormGroup>

          <FormGroup
            small-label
            :label="$t('resetPassword.repeatNewPassword')"
            required
            class="mb-32"
            :error="v$.account.passwordConfirm.$error"
          >
            <FormInput
              v-model="account.passwordConfirm"
              :error="v$.account.passwordConfirm.$error"
              type="password"
              size="large"
              @blur="v$.account.passwordConfirm.$touch"
            >
            </FormInput>

            <template #error>
              {{ $t('error.notMatchingPassword') }}
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
              {{ $t('resetPassword.submit') }}
            </Button>
          </div>
          <div>
            <ul class="auth__action-links">
              <li class="auth__action-link">
                <nuxt-link :to="{ name: 'login' }">
                  {{ $t('action.backToLogin') }}
                </nuxt-link>
              </li>
            </ul>
          </div>
        </form>
      </div>
    </div>
    <div v-if="success" class="auth__wrapper auth__wrapper--small-centered">
      <ButtonIcon icon="iconoir-check" />
      <h2>{{ $t('resetPassword.changed') }}</h2>
      <p>
        {{ $t('resetPassword.message') }}
      </p>
      <Button tag="nuxt-link" :to="{ name: 'login' }" size="large">
        {{ $t('action.backToLogin') }}
      </Button>
    </div>
  </div>
</template>

<script>
import { sameAs } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'

import PasswordInput from '@baserow/modules/core/components/helpers/PasswordInput'
import LangPicker from '@baserow/modules/core/components/LangPicker'
import { passwordValidation } from '@baserow/modules/core/validators'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import AuthService from '@baserow/modules/core/services/auth'
import { mapGetters } from 'vuex'

export default {
  components: { LangPicker, PasswordInput },
  mixins: [error],
  layout: 'login',
  setup() {
    const values = reactive({
      account: {
        password: '',
        passwordConfirm: '',
      },
    })

    const rules = computed(() => ({
      account: {
        password: passwordValidation,
        passwordConfirm: {
          sameAsPassword: sameAs(values.account.password),
        },
      },
    }))

    return {
      v$: useVuelidate(rules, values, { $lazy: true }),
      account: values.account,
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
      title: this.$t('resetPassword.title'),
    }
  },
  computed: {
    ...mapGetters({
      settings: 'settings/get',
    }),
  },
  methods: {
    async resetPassword() {
      const isFormCorrect = await this.v$.$validate()
      if (!isFormCorrect) return

      this.loading = true
      this.hideError()

      try {
        const token = this.$route.params.token
        await AuthService(this.$client).resetPassword(
          token,
          this.account.password
        )
        this.success = true
        this.loading = false
      } catch (error) {
        this.loading = false
        this.handleError(error, 'resetPassword', {
          BAD_TOKEN_SIGNATURE: new ResponseErrorMessage(
            this.$t('resetPassword.errorInvalidLinkTitle'),
            this.$t('resetPassword.errorInvalidLinkMessage')
          ),
          EXPIRED_TOKEN_SIGNATURE: new ResponseErrorMessage(
            this.$t('resetPassword.errorLinkExpiredTitle'),
            this.$t('resetPassword.errorLinkExpiredMessage')
          ),
        })
      }
    },
  },
}
</script>
