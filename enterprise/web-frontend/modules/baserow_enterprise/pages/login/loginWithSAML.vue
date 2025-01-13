<template>
  <div class="auth__wrapper">
    <div v-if="!redirectImmediately">
      <div class="auth__logo">
        <nuxt-link :to="{ name: 'index' }">
          <Logo />
        </nuxt-link>
      </div>
      <div class="auth__head">
        <h1 class="auth__head-title">
          {{ $t('loginWithSaml.signInWithSaml') }}
        </h1>
      </div>
      <form @submit.prevent="login">
        <FormGroup
          small-label
          :label="$t('field.emailAddress')"
          required
          :error="fieldHasErrors('email') || loginRequestError"
          class="mb-24"
        >
          <FormInput
            ref="email"
            v-model="values.email"
            type="email"
            size="large"
            :placeholder="$t('login.emailPlaceholder')"
            :error="fieldHasErrors('email') || loginRequestError"
            @input="loginRequestError = null"
            @blur="v$.values.email.$touch"
          ></FormInput>

          <template #error>
            <span v-if="fieldHasErrors('email')">
              <i class="iconoir-warning-triangle"></i>
              {{ $t('error.invalidEmail') }}
            </span>
            <span v-else-if="loginRequestError">
              <i class="iconoir-warning-triangle"></i>
              {{ $t('loginWithSaml.requestError') }}
            </span>
          </template>
        </FormGroup>
      </form>
      <div class="auth__action mb-32">
        <Button
          full-width
          size="large"
          :disabled="loading"
          :loading="loading"
          @click="login"
        >
          {{ $t('loginWithSaml.continueWithSaml') }}</Button
        >
      </div>
      <div>
        <ul class="auth__action-links">
          <li v-if="passwordLoginEnabled" class="auth__action-link">
            {{ $t('loginWithSaml.loginText') }}
            <nuxt-link :to="{ name: 'login' }">
              {{ $t('action.login') }}
            </nuxt-link>
          </li>
        </ul>
      </div>
    </div>
    <div v-else>
      <h2>
        {{ $t('loginWithSaml.redirecting') }}
      </h2>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { useVuelidate } from '@vuelidate/core'
import { reactive } from 'vue'
import decamelize from 'decamelize'
import { required, email } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import error from '@baserow/modules/core/mixins/error'
import workspaceInvitationToken from '@baserow/modules/core/mixins/workspaceInvitationToken'
import { SamlAuthProviderType } from '@baserow_enterprise/authProviderTypes'
import samlAuthProviderService from '@baserow_enterprise/services/samlAuthProvider'

export default {
  mixins: [form, error],
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
  async asyncData({ app, redirect, store, route }) {
    // the SuperUser must create the account using username and password
    if (store.getters['settings/get'].show_admin_signup_page === true) {
      return redirect({ name: 'signup' })
    }
    // if this page is accessed directly, load the login options to
    // populate the page with all the authentication providers
    if (!store.getters['authProvider/getLoginOptionsLoaded']) {
      await store.dispatch('authProvider/fetchLoginOptions')
    }
    const samlLoginOptions = store.getters[
      'authProvider/getLoginOptionsForType'
    ](new SamlAuthProviderType().getType())
    if (!samlLoginOptions) {
      return redirect({ name: 'login', query: route.query }) // no SAML provider enabled
    }
    // in case the email is not necessary or provided via workspace invitation,
    // redirect the user directly to the SAML provider
    const { invitation } = await workspaceInvitationToken.asyncData({
      route,
      app,
    })
    if (!samlLoginOptions.domainRequired || invitation?.email) {
      try {
        const { data } = await samlAuthProviderService(
          app.$client
        ).getSamlLoginUrl({
          email: invitation?.email,
          original: route.query.original,
        })
        return { redirectImmediately: true, redirectUrl: data.redirect_url }
      } catch (error) {
        return { values: { email: invitation?.email }, loginRequestError: true }
      }
    }
    return { redirectUrl: samlLoginOptions.redirect_url }
  },
  data() {
    return {
      loading: false,
      redirectImmediately: false,
      loginRequestError: false,
    }
  },
  computed: {
    ...mapGetters({
      passwordLoginEnabled: 'authProvider/getPasswordLoginEnabled',
    }),
  },
  mounted() {
    if (this.redirectImmediately) {
      window.location.href = this.getRedirectUrlWithValidQueryParams(
        this.redirectUrl
      )
    }
  },
  methods: {
    async login() {
      this.v$.$touch()
      this.loginRequestError = false
      if (this.v$.$invalid) {
        this.focusOnFirstError()
        return
      }

      this.loading = true
      this.hideError()

      const { original } = this.$route.query
      try {
        const { data } = await samlAuthProviderService(
          this.$client
        ).getSamlLoginUrl({
          email: this.values.email,
          original,
        })
        window.location = this.getRedirectUrlWithValidQueryParams(
          data.redirect_url
        )
      } catch (error) {
        this.loginRequestError = true
        this.loading = false
      }
    },
    getRedirectUrlWithValidQueryParams(url) {
      const parsedUrl = new URL(url)
      for (const [key, value] of Object.entries(this.$route.query)) {
        if (['language', 'workspaceInvitationToken'].includes(key)) {
          parsedUrl.searchParams.append(decamelize(key), value)
        }
      }
      return parsedUrl.toString()
    },
  },
}
</script>
