<template>
  <div class="auth__wrapper">
    <div v-if="!success">
      <div class="auth__logo">
        <nuxt-link :to="{ name: 'index' }">
          <Logo />
        </nuxt-link>
      </div>

      <div class="auth__head auth__head-title">
        <h1>{{ $t('changeEmail.title') }}</h1>
        <LangPicker />
      </div>

      <div>
        <Error :error="error"></Error>
        <div class="auth__action mb-32">
          <Button
            type="primary"
            full-width
            size="large"
            :loading="loading"
            :disabled="loading || success"
            @click="confirmEmailChange"
          >
            {{ $t('changeEmail.submit') }}
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
      </div>
    </div>
    <div v-if="success" class="auth__wrapper auth__wrapper--small-centered">
      <ButtonIcon icon="iconoir-check" />
      <h2>{{ $t('changeEmail.changed') }}</h2>
      <p>
        {{ $t('changeEmail.message') }}
      </p>
      <Button tag="nuxt-link" :to="{ name: 'login' }" size="large">
        {{ $t('action.backToLogin') }}
      </Button>
    </div>
  </div>
</template>

<script>
import LangPicker from '@baserow/modules/core/components/LangPicker'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import error from '@baserow/modules/core/mixins/error'
import AuthService from '@baserow/modules/core/services/auth'

export default {
  components: { LangPicker },
  mixins: [error],
  layout: 'login',
  data() {
    return {
      loading: false,
      success: false,
    }
  },
  head() {
    return {
      title: this.$t('changeEmail.title'),
    }
  },
  methods: {
    async confirmEmailChange() {
      this.loading = true
      this.hideError()

      try {
        const token = this.$route.params.token
        await AuthService(this.$client).changeEmail(token)
        this.success = true
        this.loading = false
      } catch (error) {
        this.loading = false
        this.handleError(error, 'changeEmail', {
          BAD_TOKEN_SIGNATURE: new ResponseErrorMessage(
            this.$t('changeEmail.errorInvalidLinkTitle'),
            this.$t('changeEmail.errorInvalidLinkMessage')
          ),
          EXPIRED_TOKEN_SIGNATURE: new ResponseErrorMessage(
            this.$t('changeEmail.errorLinkExpiredTitle'),
            this.$t('changeEmail.errorLinkExpiredMessage')
          ),
          ERROR_EMAIL_ALREADY_EXISTS: new ResponseErrorMessage(
            this.$t('changeEmail.errorEmailExistsTitle'),
            this.$t('changeEmail.errorEmailExistsMessage')
          ),
          ERROR_EMAIL_ALREADY_CHANGED: new ResponseErrorMessage(
            this.$t('changeEmail.errorEmailAlreadyChangedTitle'),
            this.$t('changeEmail.errorEmailAlreadyChangedMessage')
          ),
        })
      }
    },
  },
}
</script>
