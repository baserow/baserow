<template>
  <div
    class="auth__wrapper"
    :class="{ 'auth__wrapper--small-centered': success }"
  >
    <div v-if="!success">
      <div class="auth__logo">
        <nuxt-link :to="{ name: 'index' }">
          <Logo />
        </nuxt-link>
      </div>
      <div class="auth__head auth__head-title">
        <h1 class="margin-bottom-0">{{ $t('forgotPassword.title') }}</h1>
        <LangPicker />
      </div>

      <!-- Disabled info message -->
      <template v-if="!settings.allow_reset_password">
        <Alert type="error">
          <template #title>{{ $t('forgotPassword.disabled') }}</template>
          <p>{{ $t('forgotPassword.disabledMessage') }}</p>
        </Alert>
        <nuxt-link :to="{ name: 'login' }">
          <Button>{{ $t('action.backToLogin') }}</Button>
        </nuxt-link>
      </template>

      <!-- Form -->
      <div v-else>
        <p class="auth__head-text">
          {{ $t('forgotPassword.message') }}
        </p>
        <Error :error="error"></Error>
        <form @submit.prevent="sendLink">
          <FormGroup
            small-label
            :label="$t('field.emailAddress')"
            required
            :error="fieldHasErrors('email')"
            class="mb-32"
          >
            <FormInput
              v-model="formData.email"
              :error="fieldHasErrors('email')"
              :disabled="success"
              size="large"
              @blur="v$.email.$touch"
            >
            </FormInput>
            <template #error>
              <i class="iconoir-warning-triangle"></i>
              {{ $t('error.invalidEmail') }}
            </template>
          </FormGroup>
          <div class="auth__action mb-32">
            <Button
              type="primary"
              full-width
              size="large"
              :loading="loading"
              :disabled="loading || success"
            >
              {{ $t('forgotPassword.submit') }}
            </Button>
          </div>
          <div>
            <ul class="auth__action-links">
              <li class="auth__action-link">
                <nuxt-link :to="{ name: 'login' }">
                  {{ $t('forgotPassword.goBack') }}
                </nuxt-link>
              </li>
            </ul>
          </div>
        </form>
      </div>
    </div>
    <div v-if="success" class="auth__wrapper auth__wrapper--small-centered">
      <ButtonIcon icon="iconoir-mail" type="secondary"></ButtonIcon>
      <h2>
        {{ $t('forgotPassword.confirmationTitle') }}
      </h2>
      <p>
        {{ $t('forgotPassword.confirmation', { email: formData.email }) }}
      </p>
      <Button
        tag="nuxt-link"
        :to="{ name: 'login' }"
        type="primary"
        size="large"
      >
        {{ $t('action.backToLogin') }}</Button
      >
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { required, email } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import { useStore } from 'vuex'
import { useI18n } from 'vue-i18n'
import { useRuntimeConfig, useRouter, useHead } from '#app'

import AuthService from '@baserow/modules/core/services/auth'
import LangPicker from '@baserow/modules/core/components/LangPicker'

definePageMeta({
  layout: 'login',
})

const { t } = useI18n()
const store = useStore()
const config = useRuntimeConfig()
const router = useRouter()
const client = useNuxtApp().$client

// Data
const loading = ref(false)
const success = ref(false)
const error = ref({
  visible: false,
  title: '',
  message: '',
})

const formData = reactive({
  email: '',
})

// Vuelidate
const rules = {
  email: { required, email },
}

const v$ = useVuelidate(rules, formData, { $lazy: true })

// Computed
const settings = computed(() => store.getters['settings/get'])

// Methods
const hideError = () => {
  error.value.visible = false
}

const showError = (title, message = null) => {
  error.value.visible = true

  if (message === null) {
    error.value.title = title.title
    error.value.message = title.message
  } else {
    error.value.title = title
    error.value.message = message
  }
}

const handleError = (err, name = 'application') => {
  if (err.handler) {
    const message = err.handler.getMessage(name)
    showError(message)
    err.handler.handled()
  } else {
    throw err
  }
}

const fieldHasErrors = (field) => {
  return v$.value[field].$error
}

const sendLink = async () => {
  const isFormCorrect = await v$.value.$validate()
  if (!isFormCorrect) return

  loading.value = true
  hideError()

  try {
    const resetUrl = `${config.public.baserowEmbeddedShareUrl}/reset-password`
    await AuthService(client).sendResetPasswordEmail(formData.email, resetUrl)
    success.value = true
    loading.value = false
  } catch (err) {
    loading.value = false
    handleError(err, 'passwordReset')
  }
}

// Head
useHead({
  title: t('forgotPassword.title'),
  link: [
    {
      rel: 'canonical',
      href:
        config.public.publicWebFrontendUrl +
        router.resolve({ name: 'forgot-password' }).href,
    },
  ],
})
</script>
