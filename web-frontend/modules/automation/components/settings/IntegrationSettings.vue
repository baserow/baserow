<template>
  <ApplicationIntegrationSettings :application="automation" />
</template>

<script setup>
import ApplicationIntegrationSettings from '@baserow/modules/core/components/integrations/ApplicationIntegrationSettings'

defineProps({
  automation: {
    type: Object,
    required: true,
  },
})
</script>
