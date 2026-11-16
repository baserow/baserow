<template>
  <AgentServicePicker
    ref="picker"
    v-bind="$attrs"
    :search-placeholder="$t('agent.searchTriggerTypes')"
    :empty-text="$t('agent.noTriggerTypes')"
  />
</template>

<script setup>
import { ref } from 'vue'
import AgentServicePicker from '@baserow/modules/agent/components/configuration/AgentServicePicker'

const picker = ref(null)
defineExpose({ toggle: (target) => picker.value.toggle(target) })
</script>
