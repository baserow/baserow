<template>
  <div>
    <div v-if="!success">
      <div class="auth__logo">
        <nuxt-link :to="{ name: 'index' }">
          <Logo />
        </nuxt-link>
      </div>
      <div class="auth__head auth__head--more-margin">
        <h1 class="auth__head-title">{{ $t('resetPassword.title') }}</h1>
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
            class="margin-bottom-2"
          >
            <PasswordInput
              v-model="state.password"
              :validation-state="v$.password"
              :placeholder="$t('signup.passwordPlaceholder')"
              :error-placeholder-class="'auth__control-error'"
              :show-error-icon="true"
            />
          </FormGroup>

          <FormGroup
            small-label
            :label="$t('resetPassword.repeatNewPassword')"
            required
            class="margin-bottom-2"
            :error="v$.passwordConfirm.$error"
          >
            <FormInput
              v-model="state.passwordConfirm"
              :error="v$.passwordConfirm.$error"
              type="password"
              size="large"
              @blur="v$.passwordConfirm.$touch"
            >
            </FormInput>

            <template #error>
              {{ $t('error.notMatchingPassword') }}
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
              {{ $t('resetPassword.submit') }}
            </Button>
          </div>
          <div>
            <ul class="auth__action-links">
              <li>
                <nuxt-link :to="{ name: 'login' }">
                  <i class="iconoir-arrow-left"></i>
                  {{ $t('action.backToLogin') }}
                </nuxt-link>
              </li>
            </ul>
          </div>
        </form>
      </div>
    </div>
    <div v-if="success" class="box__message">
      <div class="box__message-icon">
        <i class="iconoir-check"></i>
      </div>
      <h1 class="box__message-title">{{ $t('resetPassword.changed') }}</h1>
      <Button
        tag="nuxt-link"
        :to="{ name: 'login' }"
        size="large"
        type="primary"
        icon="iconoir-arrow-left"
      >
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
    const state = reactive({
      password: '',
      passwordConfirm: '',
    })

    const rules = computed(() => ({
      password: passwordValidation,
      passwordConfirm: {
        sameAsPassword: sameAs(state.password),
      },
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
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }

      this.loading = true
      this.hideError()

      try {
        const token = this.$route.params.token
        await AuthService(this.$client).resetPassword(
          token,
          this.state.password
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
