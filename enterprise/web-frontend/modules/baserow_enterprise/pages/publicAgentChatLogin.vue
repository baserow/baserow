<template>
  <div class="auth__wrapper">
    <h2 class="auth__head-title">{{ $t('publicAgentChatLogin.title') }}</h2>
    <div>
      <Error :error="error"></Error>
      <form @submit.prevent="authorize">
        <FormGroup
          small-label
          required
          :helper-text="$t('publicAgentChatLogin.description')"
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
            <span>{{ v$.values.password.$errors[0]?.$message }}</span>
          </template>
        </FormGroup>
        <div class="public-view-auth__actions">
          <Button
            type="primary"
            size="large"
            :loading="loading"
            :disabled="loading"
          >
            {{ $t('publicAgentChatLogin.enter') }}
          </Button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHead, useNuxtApp, useState } from '#imports'
import { useVuelidate } from '@vuelidate/core'
import { helpers, required } from '@vuelidate/validators'

import Error from '@baserow/modules/core/components/Error'
import { setToken } from '@baserow/modules/core/utils/auth'
import { isRelativeUrl } from '@baserow/modules/core/utils/url'
import PublicAgentChatService from '@baserow_enterprise/services/publicAgentChat'

definePageMeta({ layout: 'login' })

const route = useRoute()
const router = useRouter()
const nuxtApp = useNuxtApp()
const { $client, $i18n } = nuxtApp

const detectedLocale = useState('public-agent-chat-login-locale', () => {
  return $i18n.getBrowserLocale() || $i18n.defaultLocale
})
$i18n.locale.value = detectedLocale.value
await $i18n.loadLocaleMessages(detectedLocale.value)

useHead({ title: 'Password protected chat' })

const loading = ref(false)
const error = ref({ visible: false, title: '', message: '' })
const passwordInput = ref(null)
const values = reactive({ password: '' })
const v$ = useVuelidate(
  {
    values: {
      password: {
        required: helpers.withMessage($i18n.t('error.requiredField'), required),
      },
    },
  },
  { values },
  { $lazy: true }
)

const fieldHasErrors = (name) => v$.value.values[name]?.$error || false

const authorize = async () => {
  error.value = { visible: false, title: '', message: '' }
  v$.value.$touch()
  if (v$.value.$invalid) return
  loading.value = true
  try {
    const slug = route.params.slug
    const { data } = await PublicAgentChatService($client).auth(
      slug,
      values.password
    )
    await setToken(nuxtApp, data.access_token, `agent-chat-${slug}`)
    const { original } = route.query
    if (original && isRelativeUrl(original)) {
      await router.push(original)
    } else {
      await router.push({ name: 'agent-public-chat', params: { slug } })
    }
  } catch (e) {
    const status = e.response?.status
    error.value = {
      visible: true,
      title:
        status === 429
          ? $i18n.t('publicAgentChatLogin.tooManyAttemptsTitle')
          : $i18n.t('publicAgentChatLogin.incorrectPasswordTitle'),
      message:
        status === 429
          ? $i18n.t('publicAgentChatLogin.tooManyAttempts')
          : $i18n.t('publicAgentChatLogin.incorrectPassword'),
    }
    e.handler?.handled?.()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await nextTick()
  passwordInput.value?.focus()
})
</script>
