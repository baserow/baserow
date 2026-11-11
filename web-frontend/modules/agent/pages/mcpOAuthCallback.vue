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
 * else can't connect their account, then tells the Baserow page waiting for
 * this sign-in, matched by its state.
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import MCPServerService from '@baserow/modules/agent/services/mcpServer'
import { MCP_OAUTH_MESSAGE_TYPE } from '@baserow/modules/agent/constants'
import { mcpErrorMessage } from '@baserow/modules/agent/utils/mcp'

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
  const state = String(route.query.state || '')
  let integration = null
  try {
    // Without a code the provider reports a cancelled sign-in; the request
    // still uses up the state.
    const { data } = await MCPServerService($client).completeOAuth(
      state,
      route.query.error ? '' : String(route.query.code || '')
    )
    integration = data
  } catch (e) {
    // Whatever failed, the waiting page is told, so it doesn't wait in vain.
    error.value = e.handler
      ? mcpErrorMessage(t, e).message
      : t('agent.connectedAppSignInFailed')
  }
  done.value = true
  const message = {
    type: MCP_OAUTH_MESSAGE_TYPE,
    state,
    integration,
    error: error.value,
  }
  // The channel reaches the waiting page even when the provider cut this
  // popup off from it; the opener is told too where it's still there.
  const channel = new BroadcastChannel(MCP_OAUTH_MESSAGE_TYPE)
  channel.postMessage(message)
  channel.close()
  if (window.opener) {
    window.opener.postMessage(message, window.location.origin)
  }
  window.close()
})
</script>
