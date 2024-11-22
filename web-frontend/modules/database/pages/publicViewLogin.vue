<template>
  <div class="auth__wrapper">
    <h2 class="auth__head-title">{{ $t('publicViewAuthLogin.title') }}</h2>
    <div>
      <Error :error="error"></Error>
      <form @submit.prevent="authorizeView">
        <FormGroup
          small-label
          required
          :helper-text="$t('publicViewAuthLogin.description')"
          :error="fieldHasErrors('password')"
          class="margin-bottom-2"
        >
          <FormInput
            ref="password"
            v-model="values.password"
            size="large"
            :error="fieldHasErrors('password')"
            type="password"
          ></FormInput>

          <template #error>
            {{ $t('error.passwordRequired') }}
          </template>
        </FormGroup>

        <div class="public-view-auth__actions">
          <Button
            type="primary"
            size="large"
            :loading="loading"
            :disabled="loading || $v.$invalid"
          >
            {{ $t('publicViewAuthLogin.enter') }}
          </Button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import { required } from 'vuelidate/lib/validators'
import { mapActions } from 'vuex'
import { isRelativeUrl } from '@baserow/modules/core/utils/url'
import languageDetection from '@baserow/modules/core/mixins/languageDetection'

export default {
  mixins: [form, error, languageDetection],
  layout: 'login',
  data() {
    return {
      loading: false,
      allowedValues: ['password'],
      values: {
        password: '',
      },
    }
  },
  head() {
    return {
      title: 'Password protected view',
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.$refs.password.focus()
    })
  },
  methods: {
    clearInput() {
      this.values.password = ''
    },
    async authorizeView() {
      this.hideError()
      this.loading = true

      try {
        const slug = this.$route.params.slug
        const rsp = await this.$client.post(
          `/database/views/${slug}/public/auth/`,
          { password: this.values.password }
        )
        await this.setPublicAuthToken({ slug, token: rsp.data.access_token })

        // Redirect to the original view.
        // Subsequent requests will use the token saved into the store.
        const { original } = this.$route.query
        if (original && isRelativeUrl(original)) {
          await this.$router.push(original)
        }
      } catch (e) {
        const statusCode = e.response?.status
        // hide the authorization error here and show the correct error message
        if (statusCode === 401) {
          this.$store.dispatch('toast/setAuthorizationError', false)
          this.showError(
            this.$t('publicViewAuthLogin.error.incorrectPasswordTitle'),
            this.$t('publicViewAuthLogin.error.incorrectPasswordText')
          )
        } else {
          this.handleError(e, 'auth')
        }
        this.loading = false
      }
    },
    ...mapActions({
      setPublicAuthToken: 'page/view/public/setAuthToken',
    }),
  },
  validations: {
    values: {
      password: { required },
    },
  },
}
</script>
