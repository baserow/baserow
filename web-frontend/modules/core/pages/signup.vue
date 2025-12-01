<template>
  <div class="auth__wrapper">
    <EmailNotVerified v-if="displayEmailNotVerified" :email="emailToVerify">
    </EmailNotVerified>
    <template v-if="!displayEmailNotVerified">
      <div class="auth__logo">
        <nuxt-link :to="{ name: 'index' }">
          <Logo />
        </nuxt-link>
      </div>

      <h1 class="auth__head-title">{{ $t('signup.headTitle') }}</h1>
      <div class="auth__head">
        <span class="auth__head-text">
          {{ $t('signup.loginText') }}
          <nuxt-link :to="{ name: 'login' }">
            {{ $t('action.login') }}
          </nuxt-link></span
        >
        <LangPicker />
      </div>
      <template v-if="shouldShowAdminSignupPage">
        <Alert>
          <template #title>{{ $t('signup.requireFirstUser') }}</template>
          <p>{{ $t('signup.requireFirstUserMessage') }}</p></Alert
        >
      </template>
      <template v-if="!isSignupEnabled">
        <Alert type="error">
          <template #title>{{ $t('signup.disabled') }}</template>
          <p>{{ $t('signup.disabledMessage') }}</p></Alert
        >
        <Button tag="nuxt-link" :to="{ name: 'login' }" full-width>
          {{ $t('action.backToLogin') }}</Button
        >
      </template>
      <template v-else>
        <template v-if="loginButtons.length">
          <LoginButtons :invitation="invitation" :hide-if-no-buttons="true" />

          <div class="auth__separator">
            {{ $t('common.or') }}
          </div>
        </template>

        <PasswordRegister
          v-if="passwordLoginEnabled"
          :invitation="invitation"
          @success="next"
        >
        </PasswordRegister>

        <LoginActions
          v-if="!shouldShowAdminSignupPage"
          :invitation="invitation"
        ></LoginActions>
      </template>
    </template>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import PasswordRegister from '@baserow/modules/core/components/auth/PasswordRegister'
import LangPicker from '@baserow/modules/core/components/LangPicker'
import LoginButtons from '@baserow/modules/core/components/auth/LoginButtons'
import LoginActions from '@baserow/modules/core/components/auth/LoginActions'
import workspaceInvitationToken from '@baserow/modules/core/mixins/workspaceInvitationToken'
import { EMAIL_VERIFICATION_OPTIONS } from '@baserow/modules/core/enums'
import EmailNotVerified from '@baserow/modules/core/components/auth/EmailNotVerified.vue'

export default {
  components: {
    PasswordRegister,
    LangPicker,
    LoginButtons,
    LoginActions,
    EmailNotVerified,
  },
  layout: 'login',
  async asyncData({ app, route, store, redirect }) {
    if (store.getters['auth/isAuthenticated']) {
      return redirect({ name: 'dashboard' })
    }
    await store.dispatch('authProvider/fetchLoginOptions')
    return await workspaceInvitationToken.asyncData({ route, app })
  },
  data() {
    return {
      displayEmailNotVerified: false,
      emailToVerify: null,
    }
  },
  head() {
    return {
      title: this.$t('signup.headTitle'),
      link: [
        {
          rel: 'canonical',
          href:
            this.$config.PUBLIC_WEB_FRONTEND_URL +
            this.$router.resolve({ name: 'signup' }).href,
        },
      ],
    }
  },
  computed: {
    isSignupEnabled() {
      return (
        this.settings.allow_new_signups ||
        (this.settings.allow_signups_via_workspace_invitations &&
          this.invitation?.id)
      )
    },
    shouldShowAdminSignupPage() {
      return this.settings.show_admin_signup_page
    },
    ...mapGetters({
      settings: 'settings/get',
      loginActions: 'authProvider/getAllLoginActions',
      loginButtons: 'authProvider/getAllLoginButtons',
      passwordLoginEnabled: 'authProvider/getPasswordLoginEnabled',
    }),
  },
  methods: {
    next(params) {
      if (params?.email) {
        this.emailToVerify = params.email
      }

      if (
        this.emailToVerify &&
        this.settings.email_verification ===
          EMAIL_VERIFICATION_OPTIONS.ENFORCED &&
        !this.$route.query.workspaceInvitationToken
      ) {
        this.displayEmailNotVerified = true
      } else {
        this.$nuxt.$router.push({ name: 'dashboard' }, () => {
          this.$store.dispatch('settings/hideAdminSignupPage')
        })
      }
    },
  },
}
</script>
