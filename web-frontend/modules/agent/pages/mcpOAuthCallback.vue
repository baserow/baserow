<template>
  <div class="auth__wrapper auth__wrapper--small-centered">
    <p v-if="!done">{{ $t('agent.mcpOAuthCallbackConnecting') }}</p>
    <p v-else-if="error">{{ error }}</p>
    <p v-else>{{ $t('agent.mcpOAuthCallbackConnected') }}</p>
  </div>
</template>

<script setup>
/**
 * The page an MCP server's provider sends the editor back to. It finishes the
 * sign-in with the editor's own session, so a sign-in link opened by someone
 * else can't connect their account, then tells the Baserow page that opened
 * the popup.
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import MCPServerService from '@baserow/modules/agent/services/mcpServer'
import { MCP_OAUTH_MESSAGE_TYPE } from '@baserow/modules/agent/constants'

definePageMeta({
  layout: 'login',
  middleware: ['settings', 'authenticated'],
})

const { t } = useI18n()
const { $client } = useNuxtApp()
const route = useRoute()
const done = ref(false)
const error = ref(null)
useHead({ title: t('agent.mcpOAuthCallbackConnecting') })

onMounted(async () => {
  let integrationId = null
  try {
    // Without a code the provider reports a cancelled sign-in; the request
    // still uses up the state.
    const { data } = await MCPServerService($client).completeOAuth(
      String(route.query.state || ''),
      route.query.error ? '' : String(route.query.code || '')
    )
    integrationId = data.id
  } catch (e) {
    // Whatever failed, the opener is told, so it doesn't wait in vain.
    e.handler?.handled()
    error.value =
      e.handler?.getMessage().message || t('agent.connectedAppSignInFailed')
  }
  done.value = true
  if (window.opener) {
    window.opener.postMessage(
      { type: MCP_OAUTH_MESSAGE_TYPE, integrationId, error: error.value },
      window.location.origin
    )
    window.close()
  }
})
</script>
