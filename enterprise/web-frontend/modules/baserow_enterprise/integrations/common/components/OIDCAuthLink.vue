<template>
  <div class="oidc-auth-link__wrapper">
    <template v-for="authProvider in authProviders">
      <ABButton :key="authProvider.id" @click.prevent="login(authProvider)">
        {{ getLabel(authProvider) }}
      </ABButton>
    </template>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
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
    afterLogin: {
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
    async login(authProvider) {
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
      urlWithParams.searchParams.append('iss', authProvider.base_url)

      window.location = urlWithParams.toString()
    },
  },
  validations: {},
}
</script>
