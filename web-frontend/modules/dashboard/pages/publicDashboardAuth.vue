<template>
  <div class="public-dashboard-auth">
    <div class="public-dashboard-auth__icon">
      <i class="iconoir-key-alt"></i>
    </div>
    <h1 class="public-dashboard-auth__title">
      {{ $t('publicDashboardAuth.title') }}
    </h1>
    <p class="public-dashboard-auth__description">
      {{ $t('publicDashboardAuth.description') }}
    </p>
    <Error :error="error"></Error>
    <form class="public-dashboard-auth__form" @submit.prevent="authorize">
      <FormGroup
        small-label
        required
        :label="$t('publicDashboardAuth.passwordLabel')"
        :error="v$.values.password.$error"
        class="margin-bottom-2"
      >
        <FormInput
          ref="passwordInput"
          v-model="v$.values.password.$model"
          type="password"
          size="large"
          autocomplete="current-password"
          :placeholder="$t('publicDashboardAuth.passwordPlaceholder')"
          :error="v$.values.password.$error"
        ></FormInput>

        <template #error>
          <span>{{ v$.values.password.$errors[0]?.$message }}</span>
        </template>
      </FormGroup>

      <Button
        type="primary"
        size="large"
        full-width
        :loading="loading"
        :disabled="loading"
      >
        {{ $t('publicDashboardAuth.continue') }}
      </Button>
    </form>
    <div v-if="showLogo" class="public-dashboard-auth__footer">
      <ExternalLinkBaserowLogo />
    </div>
  </div>
</template>

<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createError, useAsyncData, useNuxtApp } from '#app'
import { useHead, useState } from '#imports'
import { useVuelidate } from '@vuelidate/core'
import { helpers, required } from '@vuelidate/validators'

import Error from '@baserow/modules/core/components/Error'
import ExternalLinkBaserowLogo from '@baserow/modules/core/components/ExternalLinkBaserowLogo'
import PublicDashboardService from '@baserow/modules/dashboard/services/publicDashboard'
import { isRelativeUrl } from '@baserow/modules/core/utils/url'

/**
 * The password page of a password protected public dashboard. The right
 * password is exchanged for a token that the public dashboard page sends with
 * every request, after which the visitor is sent back to the dashboard.
 */
definePageMeta({
  layout: 'login',
})

const route = useRoute()
const router = useRouter()
const { $store, $client, $i18n } = useNuxtApp()
const slug = route.params.slug

// Visitors see the page in the language of their browser, like the dashboard.
const originalLocale = ref($i18n.locale.value)
const detectedLocale = useState('public-dashboard-auth-detected-locale', () => {
  return $i18n.getBrowserLocale() || $i18n.defaultLocale
})
$i18n.locale.value = detectedLocale.value
await $i18n.loadLocaleMessages(detectedLocale.value)

// The owner may have hidden the Baserow logo on the shared dashboard, which
// applies to its password page as well.
const { data: authInfo, error: authInfoError } = await useAsyncData(
  `dashboard-public-auth-${slug}`,
  async () => {
    const { $client } = useNuxtApp()

    try {
      const { data } = await PublicDashboardService($client).fetchAuthInfo(slug)
      return data
    } catch (e) {
      const statusCode = e.response?.status

      if (statusCode === 404) {
        throw createError({
          statusCode: 404,
          message: 'Dashboard not found.',
          data: {
            report: false,
          },
          fatal: true,
        })
      }

      throw createError({
        statusCode: statusCode || 500,
        message: e.message || 'Error loading dashboard.',
        fatal: true,
      })
    }
  }
)

if (authInfoError.value) {
  throw authInfoError.value
}

const showLogo = computed(() => authInfo.value?.show_logo !== false)

useHead(() => {
  const head = { title: $i18n.t('publicDashboardAuth.title') }
  if (!showLogo.value) {
    head.titleTemplate = '%s'
  }
  return head
})

const loading = ref(false)
const error = ref({ visible: false, title: '', message: '' })
const passwordInput = ref(null)

const values = reactive({ password: '' })
const rules = {
  values: {
    password: {
      required: helpers.withMessage($i18n.t('error.requiredField'), required),
    },
  },
}
const v$ = useVuelidate(rules, { values }, { $lazy: true })

const showError = (title, message) => {
  error.value = { visible: true, title, message }
}

const hideError = () => {
  error.value = { visible: false, title: '', message: '' }
}

const authorize = async () => {
  v$.value.$touch()
  if (v$.value.$invalid) {
    return
  }

  hideError()
  loading.value = true

  try {
    const { data } = await PublicDashboardService($client).auth(
      slug,
      values.password
    )
    await $store.dispatch('dashboardApplication/setPublicAuthToken', {
      slug,
      token: data.access_token,
    })

    // Back to the page that sent the visitor here, as long as it is one of
    // ours, otherwise to the dashboard itself.
    const { original } = route.query
    await router.push(
      original && isRelativeUrl(original)
        ? original
        : { name: 'dashboard-public', params: { slug } }
    )
  } catch (e) {
    if (e.response?.status === 401) {
      showError(
        $i18n.t('publicDashboardAuth.incorrectPasswordTitle'),
        $i18n.t('publicDashboardAuth.incorrectPasswordText')
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

onBeforeUnmount(() => {
  $i18n.locale.value = originalLocale.value
})
</script>
