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
            ref="emailInput"
            v-model="formData.email"
            type="email"
            size="large"
            :placeholder="$t('login.emailPlaceholder')"
            :error="fieldHasErrors('email') || loginRequestError"
            @input="loginRequestError = false"
            @blur="v$.email.$touch"
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

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { useVuelidate } from '@vuelidate/core'
import { required, email } from '@vuelidate/validators'
import decamelize from 'decamelize'

import { SamlAuthProviderType } from '@baserow_enterprise/authProviderTypes'
import samlAuthProviderService from '@baserow_enterprise/services/samlAuthProvider'
import WorkspaceService from '@baserow/modules/core/services/workspace'

definePageMeta({
  layout: 'login',
})

const store = useStore()
const route = useRoute()
const { $client } = useNuxtApp()

// Refs
const emailInput = ref(null)
const loading = ref(false)
const loginRequestError = ref(false)
const redirectImmediately = ref(false)
const redirectUrl = ref(null)

// Form data
const formData = reactive({
  email: '',
})

// Vuelidate
const rules = {
  email: { required, email },
}

const v$ = useVuelidate(rules, formData, { $lazy: true })

// Computed
const passwordLoginEnabled = computed(
  () => store.getters['authProvider/getPasswordLoginEnabled']
)

// Methods
const fieldHasErrors = (field) => {
  return v$.value[field].$error
}

const getRedirectUrlWithValidQueryParams = (url) => {
  const parsedUrl = new URL(url)
  for (const [key, value] of Object.entries(route.query)) {
    if (['language', 'workspaceInvitationToken'].includes(key)) {
      parsedUrl.searchParams.append(decamelize(key), value)
    }
  }
  return parsedUrl.toString()
}

const login = async () => {
  v$.value.$touch()
  loginRequestError.value = false

  if (v$.value.$invalid) {
    emailInput.value?.$el?.focus()
    return
  }

  loading.value = true

  const { original } = route.query
  try {
    const { data } = await samlAuthProviderService($client).getSamlLoginUrl({
      email: formData.email,
      original,
    })
    window.location = getRedirectUrlWithValidQueryParams(data.redirect_url)
  } catch (error) {
    loginRequestError.value = true
    loading.value = false
  }
}

// Async data fetching
const { data: asyncData } = await useAsyncData('saml-login', async () => {
  // the SuperUser must create the account using username and password
  if (store.getters['settings/get'].show_admin_signup_page === true) {
    await navigateTo({ name: 'signup' })
    return {}
  }

  // if this page is accessed directly, load the login options to
  // populate the page with all the authentication providers
  if (!store.getters['authProvider/getLoginOptionsLoaded']) {
    await store.dispatch('authProvider/fetchLoginOptions')
  }

  const samlLoginOptions = store.getters['authProvider/getLoginOptionsForType'](
    new SamlAuthProviderType().getType()
  )

  if (!samlLoginOptions) {
    await navigateTo({ name: 'login', query: route.query }) // no SAML provider enabled
    return {}
  }

  // Fetch workspace invitation if token exists
  let invitation = null
  const invitationToken = route.query.workspaceInvitationToken
  if (invitationToken) {
    try {
      const { data } =
        await WorkspaceService($client).fetchInvitationByToken(invitationToken)
      invitation = data
    } catch {}
  }

  // in case the email is not necessary or provided via workspace invitation,
  // redirect the user directly to the SAML provider
  if (!samlLoginOptions.domainRequired || invitation?.email) {
    try {
      const { data } = await samlAuthProviderService($client).getSamlLoginUrl({
        email: invitation?.email,
        original: route.query.original,
      })
      return {
        redirectImmediately: true,
        redirectUrl: data.redirect_url,
      }
    } catch (error) {
      return {
        email: invitation?.email,
        loginRequestError: true,
      }
    }
  }

  return { redirectUrl: samlLoginOptions.redirect_url }
})

// Apply async data results
if (asyncData.value?.redirectImmediately) {
  redirectImmediately.value = true
  redirectUrl.value = asyncData.value.redirectUrl
}
if (asyncData.value?.redirectUrl) {
  redirectUrl.value = asyncData.value.redirectUrl
}
if (asyncData.value?.email) {
  formData.email = asyncData.value.email
}
if (asyncData.value?.loginRequestError) {
  loginRequestError.value = true
}

// Mounted
onMounted(() => {
  if (redirectImmediately.value && redirectUrl.value) {
    window.location.href = getRedirectUrlWithValidQueryParams(redirectUrl.value)
  }
})
</script>
