<template>
  <div class="auth__wrapper">
    <h2 class="auth__head-title">{{ $t('publicViewAuthLogin.title') }}</h2>
    <div>
      <Error :error="error"></Error>
      <client-only>
        <form @submit.prevent="authorizeView">
          <FormGroup
            v-if="v$.password"
            small-label
            required
            :helper-text="$t('publicViewAuthLogin.description')"
            :error="v$.password?.$error"
            class="margin-bottom-2"
          >
            <FormInput
              ref="password"
              v-model="v$.password.$model"
              size="large"
              :error="v$.password.$error"
              type="password"
            ></FormInput>

            <template #error>
              <span v-if="v$.password.required.$invalid">
                {{ $t('error.passwordRequired') }}
              </span>
            </template>
          </FormGroup>

          <div class="public-view-auth__actions">
            <Button
              type="primary"
              size="large"
              :loading="loading"
              :disabled="loading"
            >
              {{ $t('publicViewAuthLogin.enter') }}
            </Button>
          </div>
        </form>
      </client-only>
    </div>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import { required } from '@vuelidate/validators'
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
      values: null,
      v$: null,
    }
  },
  head() {
    return {
      title: 'Password protected view',
    }
  },
  created() {
    const values = reactive({
      password: '',
    })

    const rules = computed(() => ({
      password: { required },
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
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
}
</script>
