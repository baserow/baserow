<template>
  <div>
    <component
      :is="twoFactorComponent"
      v-if="twoFactorRequired"
      :email="twoFactorEmail"
      :token="twoFaToken"
      @success="success"
      @expired="twoFactorExpired"
    />
    <EmailNotVerified
      v-else-if="displayEmailNotVerified"
      :email="emailToVerify"
    >
    </EmailNotVerified>
    <template v-else>
      <div v-if="displayHeader">
        <div class="auth__logo">
          <nuxt-link :to="{ name: 'index' }">
            <Logo />
          </nuxt-link>
        </div>
        <h1 class="auth__head-title">{{ $t('login.title') }}</h1>
        <div class="auth__head">
          <span v-if="settings.allow_new_signups" class="auth__head-text">
            {{ $t('login.signUpText') }}
            <nuxt-link :to="{ name: 'signup' }">
              {{ $t('login.signUp') }}
            </nuxt-link></span
          >
          <LangPicker class="margin-left-auto" />
        </div>
      </div>
      <div v-if="redirectByDefault && defaultRedirectUrl">
        {{ $t('login.redirecting') }}
      </div>
      <div v-else>
        <template v-if="!passwordLoginHidden && loginButtons.length">
          <LoginButtons
            :hide-if-no-buttons="loginButtonsCompact"
            :invitation="invitation"
            :original="original"
          />

          <div class="auth__separator">
            {{ $t('common.or') }}
          </div>
        </template>

        <PasswordLogin
          v-if="!passwordLoginHidden"
          :invitation="invitation"
          :display-forgot-password="
            settings.allow_reset_password && !passwordLoginHidden
          "
          @success="success"
          @two-factor-auth="setTwoFactorRequired"
          @email-not-verified="emailNotVerified"
        >
        </PasswordLogin>

        <LoginActions :invitation="invitation" :original="original">
          <li v-if="passwordLoginHidden" class="auth__action-link">
            <a @click="passwordLoginHiddenIfDisabled = false">
              {{ $t('login.displayPasswordLogin') }}
            </a>
          </li>
        </LoginActions>
      </div>
    </template>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import EmailNotVerified from '@baserow/modules/core/components/auth/EmailNotVerified.vue'
import LoginButtons from '@baserow/modules/core/components/auth/LoginButtons'
import LoginActions from '@baserow/modules/core/components/auth/LoginActions'
import PasswordLogin from '@baserow/modules/core/components/auth/PasswordLogin'
import LangPicker from '@baserow/modules/core/components/LangPicker'
import {
  isRelativeUrl,
  addQueryParamsToRedirectUrl,
} from '@baserow/modules/core/utils/url'
import TOTPLogin from '@baserow/modules/core/components/auth/TOTPLogin'

export default {
  components: {
    TOTPLogin,
    PasswordLogin,
    LoginButtons,
    LangPicker,
    LoginActions,
    EmailNotVerified,
  },
  props: {
    original: {
      type: String,
      required: false,
      default: null,
    },
    redirectOnSuccess: {
      type: Boolean,
      required: false,
      default: true,
    },
    displayHeader: {
      type: Boolean,
      required: false,
      default: true,
    },
    invitation: {
      required: false,
      validator: (prop) => typeof prop === 'object' || prop === null,
      default: null,
    },
    loginButtonsCompact: {
      type: Boolean,
      required: false,
      default: false,
    },
    redirectByDefault: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      passwordLoginHiddenIfDisabled: true,
      displayEmailNotVerified: false,
      emailToVerify: null,
      twoFactorComponent: null,
      twoFactorRequired: false,
      twoFactorEmail: null,
      twoFaToken: null,
    }
  },
  computed: {
    ...mapGetters({
      settings: 'settings/get',
      loginActions: 'authProvider/getAllLoginActions',
      loginButtons: 'authProvider/getAllLoginButtons',
      passwordLoginEnabled: 'authProvider/getPasswordLoginEnabled',
    }),
    computedOriginal() {
      let original = this.original
      if (!original) {
        original = this.$route.query.original
      }
      return original
    },
    passwordLoginHidden() {
      return this.passwordLoginHiddenIfDisabled && !this.passwordLoginEnabled
    },
    defaultRedirectUrl() {
      return this.$store.getters['authProvider/getDefaultRedirectUrl']
    },
  },
  mounted() {
    if (this.redirectByDefault) {
      if (this.defaultRedirectUrl !== null) {
        const { workspaceInvitationToken } = this.$route.query
        const url = addQueryParamsToRedirectUrl(this.defaultRedirectUrl, {
          original: this.computedOriginal,
          workspaceInvitationToken,
        })
        window.location = url
      }
    }
  },
  methods: {
    async success() {
      if (this.redirectOnSuccess) {
        const original = this.computedOriginal
        if (original && isRelativeUrl(original)) {
          await this.$nuxt.$router.push(original)
        } else {
          await this.$nuxt.$router.push({ name: 'dashboard' })
        }
      }
      this.$emit('success')
    },
    emailNotVerified(email) {
      this.displayEmailNotVerified = true
      this.emailToVerify = email
    },
    setTwoFactorRequired(type, email, token) {
      const twoFaType = this.$registry.get('twoFactorAuth', type)
      this.twoFactorComponent = twoFaType.loginComponent
      this.twoFactorRequired = true
      this.twoFactorEmail = email
      this.twoFaToken = token
    },
    twoFactorExpired() {
      this.twoFaToken = null
      this.twoFactorRequired = false
      this.twoFactorComponent = null
    },
  },
}
</script>
