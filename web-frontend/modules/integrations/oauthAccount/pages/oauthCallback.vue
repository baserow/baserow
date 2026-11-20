<template>
  <div class="auth__wrapper auth__wrapper--small-centered">
    <p v-if="adminApproved">
      {{ $t('oauthAccountCallback.adminApproved') }}
    </p>
    <p v-else-if="!done">
      {{ $t('oauthAccountCallback.connecting', { provider }) }}
    </p>
    <p v-else-if="errorMessage">{{ errorMessage }}</p>
    <p v-else>{{ $t('oauthAccountCallback.connected', { provider }) }}</p>
  </div>
</template>

<script setup>
/**
 * The page a provider sends the person back to after signing in, for every
 * integration type that connects an account: its redirect URI is
 * `/integrations/<type>/oauth-callback`. It finishes the sign-in with the
 * person's own session, so a sign-in link opened by someone else can't connect
 * their account, then tells the Baserow page waiting for this sign-in, matched
 * by its state. An admin approving Baserow for their organisation is sent here
 * too, with no sign-in to finish.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import OAuthAccountService from '@baserow/modules/integrations/oauthAccount/services/oauthAccount'
import {
  isIntegrationTypeName,
  oauthMessageType,
} from '@baserow/modules/integrations/oauthAccount/constants'
import { oauthErrorMessage } from '@baserow/modules/integrations/oauthAccount/utils'
import { OAuthAccountIntegrationType } from '@baserow/modules/integrations/oauthAccount/integrationTypes'
import { announceOAuthResult } from '@baserow/modules/core/utils/oauthPopup'

definePageMeta({
  layout: 'login',
  middleware: ['settings', 'authenticated'],
})

const { t } = useI18n()
const { $client, $registry } = useNuxtApp()
const route = useRoute()
const integrationType = String(route.params.integrationType || '')
// Only a registered type that connects an account: the name goes in an API
// path, and a crafted link must not send this page's request elsewhere.
const knownType = computed(() => {
  if (!isIntegrationTypeName(integrationType)) return null
  try {
    const type = $registry.get('integration', integrationType)
    return type instanceof OAuthAccountIntegrationType ? type : null
  } catch {
    return null
  }
})
const provider = computed(() => knownType.value?.providerName || '')
const done = ref(false)
const error = ref(null)
const adminApproved = computed(
  () => !route.query.state && route.query.admin_consent !== undefined
)
const errorMessage = computed(() =>
  error.value ? oauthErrorMessage(t, error.value.code, provider.value) : null
)
useHead({
  title: t('oauthAccountCallback.connecting', { provider: provider.value }),
})

onMounted(async () => {
  if (adminApproved.value) return
  if (!knownType.value) {
    // Nothing is waiting for a sign-in of a type that doesn't exist.
    error.value = { code: null, detail: null }
    done.value = true
    return
  }
  const state = String(route.query.state || '')
  let result = null
  // Plain, not the reactive `error`: a proxy can't be posted to a channel.
  let failure = null
  try {
    const { data } = await OAuthAccountService(
      $client,
      integrationType
    ).complete({
      state,
      code: String(route.query.code || ''),
      error: String(route.query.error || ''),
      errorDescription: String(route.query.error_description || ''),
    })
    result = data
  } catch (e) {
    // Whatever failed, the waiting page is told, so it doesn't wait in vain.
    e.handler?.handled()
    failure = {
      code: e.handler?.code || null,
      detail: e.handler?.detail || null,
    }
    error.value = failure
  }
  done.value = true
  announceOAuthResult({
    type: oauthMessageType(integrationType),
    state,
    created: result?.created ?? false,
    integration: result?.integration ?? null,
    error: failure,
  })
  window.close()
})
</script>
