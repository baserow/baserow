<template>
  <div>
    <ABButton
      @click.prevent="login()"
      class="oidc-auth-link"
      v-for="authProvider in authProviders"
      :key="authProvider.id"
    >
      {{ getLabel(authProvider) }}
    </ABButton>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import ThemeProvider from '@baserow/modules/builder/components/theme/ThemeProvider'

export default {
  components: { ThemeProvider },
  mixins: [form],
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
  },
  data() {
    return {
      loading: false,
      values: { email: '' },
    }
  },
  computed: {},
  methods: {
    getLabel(authProvider) {
      return this.$t('oidcAuthLink.placeholderWithOIDC', {
        login: this.loginButtonLabel,
        provider: this.authProviderType.getProviderName(authProvider),
      })
    },
    async login() {
      await this.beforeLogin()

      this.loading = true

      const dest = `${
        this.$config.PUBLIC_BACKEND_URL
      }/api/user-source/${encodeURIComponent(
        this.userSource.uid
      )}/sso/oauth2/openid_connect/login/`

      const urlWithParams = new URL(dest)

      // Add the current url as get parameter to be redirected here after the login.
      urlWithParams.searchParams.append('original', window.location)

      window.location = urlWithParams.toString()
    },
  },
  validations: {},
}
</script>
