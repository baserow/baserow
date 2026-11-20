<template>
  <div>
    <p>
      {{
        integration.connected
          ? integration.account_email
          : $t('googleIntegration.disconnected')
      }}
    </p>
    <Button
      :loading="loading"
      :disabled="loading || disabled"
      @click="connect"
      >{{
        $t(
          integration.connected
            ? 'googleIntegration.reconnect'
            : 'googleIntegration.connect'
        )
      }}</Button
    >
    <Button
      v-if="integration.connected"
      type="secondary"
      :disabled="loading || disabled"
      @click="disconnect"
      >{{ $t('googleIntegration.disconnect') }}</Button
    >
    <p v-if="error">{{ $t('googleIntegration.failed') }}</p>
  </div>
</template>
<script setup>
import { onBeforeUnmount, ref } from 'vue'
const props = defineProps({
  integration: { type: Object, required: true },
  application: { type: Object, required: true },
  serviceType: { type: String, default: undefined },
  disabled: Boolean,
})
const { $client, $store } = useNuxtApp()
const loading = ref(false)
const error = ref(false)
let channel
let popup
let closeTimer

async function update(integration) {
  await $store.dispatch('integration/forceUpdate', {
    application: props.application,
    integration: props.integration,
    values: integration,
  })
}
function cleanup() {
  channel?.close()
  clearInterval(closeTimer)
  loading.value = false
}
onBeforeUnmount(cleanup)

/** Open the provider from a user click and accept only this flow's callback. */
async function connect() {
  error.value = false
  loading.value = true
  popup = window.open('about:blank', '_blank', 'width=600,height=750')
  if (!popup) {
    loading.value = false
    error.value = true
    return
  }
  try {
    const { data } = await $client.post(
      `/integrations/google/${props.integration.id}/oauth/start/`,
      { service_type: props.serviceType }
    )
    const state = new URL(data.authorization_url).searchParams.get('state')
    channel = new BroadcastChannel('baserow-google-oauth')
    channel.onmessage = async ({ data }) => {
      if (data.state !== state) return
      error.value = !!data.error
      if (data.integration) await update(data.integration)
      cleanup()
    }
    popup.location = data.authorization_url
    closeTimer = setInterval(() => {
      if (popup.closed) cleanup()
    }, 1000)
  } catch {
    popup.close()
    cleanup()
    error.value = true
  }
}
async function disconnect() {
  loading.value = true
  error.value = false
  try {
    const { data } = await $client.post(
      `/integrations/google/${props.integration.id}/oauth/disconnect/`
    )
    await update(data)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}
</script>
