<template>
  <ApplicationIntegrationSettings
    :application="builder"
    @deleted="redispatchDataSources"
  />
</template>

<script setup>
import { useStore } from 'vuex'
import ApplicationIntegrationSettings from '@baserow/modules/core/components/integrations/ApplicationIntegrationSettings'

const props = defineProps({
  builder: {
    type: Object,
    required: true,
  },
})

const store = useStore()

/**
 * Re-dispatches the data sources that used the deleted integration so their
 * bound collection elements reset (they're now misconfigured). The initiator
 * doesn't receive its own websocket echo, so this is triggered here too.
 */
function redispatchDataSources(integration) {
  store.dispatch('dataSource/redispatchForIntegration', {
    builder: props.builder,
    integrationId: integration.id,
  })
}
</script>
