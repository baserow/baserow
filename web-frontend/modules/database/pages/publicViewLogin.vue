<template>
  <div class="auth__wrapper">
    <h2 class="auth__head-title">{{ $t('publicViewAuthLogin.title') }}</h2>
    <div>
      <Error :error="error"></Error>
      <form @submit.prevent="authorizeView">
        <FormGroup
          small-label
          required
          :helper-text="$t('publicViewAuthLogin.description')"
          :error="fieldHasErrors('password')"
          class="margin-bottom-2"
        >
          <FormInput
            ref="passwordInput"
            v-model="v$.values.password.$model"
            size="large"
            :error="fieldHasErrors('password')"
            type="password"
          ></FormInput>

          <template #error>
            <span>
              {{ v$.values.password.$errors[0]?.$message }}
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
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHead } from '#imports'
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'

import Error from '@baserow/modules/core/components/Error'
import { isRelativeUrl } from '@baserow/modules/core/utils/url'

definePageMeta({
  layout: 'login',
})

const route = useRoute()
const router = useRouter()
const nuxtApp = useNuxtApp()
const { $store, $client, $i18n } = nuxtApp

// Language detection (replaces languageDetection mixin)
const originalLanguageBeforeDetect = ref(null)
originalLanguageBeforeDetect.value = $i18n.locale
$i18n.locale = $i18n.getBrowserLocale()

// Page title
useHead({
  title: 'Password protected view',
})

// Form state
const loading = ref(false)
const error = ref({ visible: false, title: '', message: '' })
const passwordInput = ref(null)

// Vuelidate setup
const values = reactive({ password: '' })
const rules = {
  values: {
    password: {
      required: helpers.withMessage($i18n.t('error.requiredField'), required),
    },
  },
}
const v$ = useVuelidate(rules, { values }, { $lazy: true })

function fieldHasErrors(fieldName) {
  return v$.value.values[fieldName]?.$error || false
}

function showError(title, message) {
  error.value = { visible: true, title, message }
}

function hideError() {
  error.value = { visible: false, title: '', message: '' }
}

async function authorizeView() {
  hideError()
  loading.value = true

  try {
    const slug = route.params.slug
    const rsp = await $client.post(`/database/views/${slug}/public/auth/`, {
      password: values.password,
    })

    await $store.dispatch('page/view/public/setAuthToken', {
      slug,
      token: rsp.data.access_token,
    })

    const { original } = route.query
    if (original && isRelativeUrl(original)) {
      router.push(original)
    }
  } catch (e) {
    const statusCode = e.response?.status
    if (statusCode === 401) {
      $store.dispatch('toast/setAuthorizationError', false)
      showError(
        $i18n.t('publicViewAuthLogin.error.incorrectPasswordTitle'),
        $i18n.t('publicViewAuthLogin.error.incorrectPasswordText')
      )
    } else {
      showError(
        $i18n.t('error.errorTitle'),
        e.message || $i18n.t('error.errorMessage')
      )
    }
    loading.value = false
  }
}

onMounted(() => {
  nextTick(() => {
    passwordInput.value?.focus()
  })
})
</script>
