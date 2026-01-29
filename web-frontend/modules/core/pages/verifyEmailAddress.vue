<template>
  <div class="auth__wrapper">
    <div class="auth__wrapper auth__wrapper--small-centered">
      <ButtonIcon icon="iconoir-mail-out" />
      <p>
        {{ $t('verifyEmailAddress.confirmation') }}
      </p>
      <p v-if="emailMismatchWarning">
        {{ $t('verifyEmailAddress.emailMismatchWarning') }}
      </p>
      <Button
        tag="nuxt-link"
        :to="{ name: 'login' }"
        type="secondary"
        size="large"
      >
        {{ $t('verifyEmailAddress.goToDashboard') }}</Button
      >
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import AuthService from '@baserow/modules/core/services/auth'
import {
  setToken,
  setUserSessionCookie,
} from '@baserow/modules/core/utils/auth'

definePageMeta({
  layout: 'login',
})

const nuxtApp = useNuxtApp()
const { $store: store, $client } = nuxtApp
const route = useRoute()
const { t } = useI18n()

const { data: result, error } = await useAsyncData('verify-email', async () => {
  const token = route.params.token
  try {
    const isAuthenticated = store.getters['auth/isAuthenticated']
    const { data } = await AuthService($client).verifyEmail(token)

    if (!isAuthenticated) {
      store.dispatch('auth/setUserData', data)
      await setToken(nuxtApp, data.refresh_token)
      await setUserSessionCookie(nuxtApp, data.user_session)
    } else {
      const loggedInUserEmail = store.getters['auth/getUserObject'].username
      if (data.email !== loggedInUserEmail) {
        return { emailMismatch: true }
      } else {
        store.dispatch('auth/forceUpdateUserData', {
          user: {
            email_verified: true,
          },
        })
      }
    }
    return { emailMismatch: false }
  } catch (err) {
    if (err.handler) {
      const response = err.handler.response
      if (response && response.status === 401) {
        if (response.data?.error === 'ERROR_DEACTIVATED_USER') {
          throw createError({
            statusCode: 401,
            message: t('error.disabledAccountMessage'),
          })
        } else if (response.data?.error === 'ERROR_AUTH_PROVIDER_DISABLED') {
          throw createError({
            statusCode: 401,
            message: t('verifyEmailAddress.disabledPasswordProvider'),
          })
        }
      }
    }
    throw createError({
      statusCode: 404,
      message: t('verifyEmailAddress.invalidToken'),
    })
  }
})

if (error.value) {
  throw error.value
}

const emailMismatchWarning = computed(
  () => result.value?.emailMismatch === true
)
</script>
