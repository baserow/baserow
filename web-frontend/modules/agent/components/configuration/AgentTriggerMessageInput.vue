<template>
  <AgentFormulaInput
    v-bind="$attrs"
    :data-providers-allowed="['trigger']"
    allow-node-selection="array"
    @update:model-value="$emit('update:modelValue', $event)"
  />
</template>

<script setup>
import AgentFormulaInput from '@baserow/modules/agent/components/configuration/AgentFormulaInput'

defineEmits(['update:modelValue'])
</script>
