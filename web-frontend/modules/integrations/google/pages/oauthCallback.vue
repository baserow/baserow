<template>
  <div class="auth__wrapper auth__wrapper--small-centered">
    <p v-if="!done">{{ $t('googleIntegration.connecting') }}</p>
    <p v-else-if="error">{{ error }}</p>
    <p v-else>{{ $t('googleIntegration.connected') }}</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const GOOGLE_OAUTH_MESSAGE_TYPE = 'baserow-google-oauth'

definePageMeta({
  layout: 'login',
  middleware: ['settings', 'authenticated'],
})

const { t } = useI18n()
const { $client } = useNuxtApp()
const route = useRoute()
const done = ref(false)
const error = ref(null)
useHead({ title: t('googleIntegration.connecting') })

onMounted(async () => {
  const state = String(route.query.state || '')
  let integration = null
  try {
    // Without a code the provider reports a cancelled sign-in; the request
    // still uses up the state.
    const { data } = await $client.post(
      '/integrations/google/oauth/complete/',
      { state, code: route.query.error ? '' : String(route.query.code || '') }
    )
    integration = data
  } catch (e) {
    // Whatever failed, the waiting page is told, so it doesn't wait in vain.
    error.value = t('googleIntegration.failed')
  }
  done.value = true
  const message = {
    type: GOOGLE_OAUTH_MESSAGE_TYPE,
    state,
    integration,
    error: error.value,
  }
  // The channel reaches the waiting page even when the provider cut this
  // popup off from it; the opener is told too where it's still there.
  const channel = new BroadcastChannel(GOOGLE_OAUTH_MESSAGE_TYPE)
  channel.postMessage(message)
  channel.close()
  if (window.opener) {
    window.opener.postMessage(message, window.location.origin)
  }
  window.close()
})
</script>
