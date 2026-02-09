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

<script setup>
import { ref, computed } from 'vue'
import { useStore } from 'vuex'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import PasswordRegister from '@baserow/modules/core/components/auth/PasswordRegister'
import LangPicker from '@baserow/modules/core/components/LangPicker'
import LoginButtons from '@baserow/modules/core/components/auth/LoginButtons'
import LoginActions from '@baserow/modules/core/components/auth/LoginActions'
import EmailNotVerified from '@baserow/modules/core/components/auth/EmailNotVerified.vue'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { EMAIL_VERIFICATION_OPTIONS } from '@baserow/modules/core/enums'

definePageMeta({
  layout: 'login',
  middleware: ['settings'],
})

const store = useStore()
const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const config = useRuntimeConfig()
const { $client } = useNuxtApp()

// Reactive data
const displayEmailNotVerified = ref(false)
const emailToVerify = ref(null)

// Fetch invitation data based on token
const invitationToken = route.query.workspaceInvitationToken
const { data: invitation } = await useAsyncData(
  `signup-invitation-${invitationToken || 'none'}`,
  async () => {
    // Redirect if already authenticated
    if (store.getters['auth/isAuthenticated']) {
      await navigateTo({ name: 'dashboard' })
      return null
    }

    // Fetch login options
    await store.dispatch('authProvider/fetchLoginOptions')

    // Fetch workspace invitation if token exists
    if (invitationToken) {
      try {
        const { data } =
          await WorkspaceService($client).fetchInvitationByToken(
            invitationToken
          )
        return data
      } catch {
        return null
      }
    }

    return null
  }
)

// Computed properties
const settings = computed(() => store.getters['settings/get'])
const loginActions = computed(
  () => store.getters['authProvider/getAllLoginActions']
)
const loginButtons = computed(
  () => store.getters['authProvider/getAllLoginButtons']
)
const passwordLoginEnabled = computed(
  () => store.getters['authProvider/getPasswordLoginEnabled']
)

const isSignupEnabled = computed(() => {
  return (
    settings.value.allow_new_signups ||
    (settings.value.allow_signups_via_workspace_invitations &&
      invitation.value?.id)
  )
})

const shouldShowAdminSignupPage = computed(() => {
  return settings.value.show_admin_signup_page
})

// Methods
const next = (params) => {
  if (params?.email) {
    emailToVerify.value = params.email
  }

  if (
    emailToVerify.value &&
    settings.value.email_verification === EMAIL_VERIFICATION_OPTIONS.ENFORCED &&
    !route.query.workspaceInvitationToken
  ) {
    displayEmailNotVerified.value = true
  } else {
    router.push({ name: 'dashboard' }).then(() => {
      store.dispatch('settings/hideAdminSignupPage')
    })
  }
}

// Head metadata
useHead({
  title: t('signup.headTitle'),
  link: [
    {
      rel: 'canonical',
      href:
        config.public.publicWebFrontendUrl +
        router.resolve({ name: 'signup' }).href,
    },
  ],
})
</script>
